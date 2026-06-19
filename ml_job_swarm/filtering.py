from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from typing import Any, Mapping

from ml_job_swarm.db.connection import StoreConnection
from ml_job_swarm.llm import (
    FitGateClient,
    FitGatePayload,
    FitGateResponse,
    LLMRequest,
    record_llm_request,
)
from ml_job_swarm.models import RulesOutcome
from ml_job_swarm.profile import current_profile_version
from pydantic import ValidationError


@dataclass(frozen=True)
class Job:
    title: str
    location_text: str | None = None
    remote_mode: str | None = None
    seniority: str | None = None
    description_text: str | None = None
    requirements_text: str | None = None


@dataclass(frozen=True)
class Company:
    name: str
    categories: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    stage: str | None = None


@dataclass(frozen=True)
class TargetProfile:
    role: str | None = None
    titles: tuple[str, ...] = ()
    level: str | None = None
    locations: tuple[str, ...] = ()
    work_mode: str | None = None
    company_stage: str | None = None
    keywords: tuple[str, ...] = ()


@dataclass(frozen=True)
class RulesFilterResult:
    outcome: RulesOutcome
    score: int
    reasons: tuple[str, ...]
    risks: tuple[str, ...]


@dataclass(frozen=True)
class JobFitResult:
    job_id: int
    title: str
    fit_score: int
    label: str
    reasons: tuple[str, ...]
    risks: tuple[str, ...]
    recommendation: str
    decision: str | None = None
    notes: str = ""


@dataclass(frozen=True)
class RulesPreviewJob:
    job_id: int
    title: str
    company_name: str
    location_text: str | None
    remote_mode: str | None
    score: int
    outcome: RulesOutcome
    reasons: tuple[str, ...]
    risks: tuple[str, ...]


@dataclass(frozen=True)
class CompanyResult:
    company_id: int
    name: str
    visible_jobs: list[JobFitResult]
    mismatch_risk_jobs: list[JobFitResult]
    hidden_jobs: list[JobFitResult]
    filtered_out_count: int

    @property
    def mismatch_risk_count(self) -> int:
        return len(self.mismatch_risk_jobs)

    @property
    def hidden_count(self) -> int:
        return len(self.hidden_jobs)

    @property
    def saved_count(self) -> int:
        return sum(
            1
            for job in (
                *self.visible_jobs,
                *self.mismatch_risk_jobs,
                *self.hidden_jobs,
            )
            if job.decision == "saved"
        )


@dataclass(frozen=True)
class ProfileReviewBatchResult:
    review_ids: list[int]
    failures: int


_WORD_RE = re.compile(r"[a-z0-9]+")
_SENIORITY = {
    "intern": "intern",
    "internship": "intern",
    "entry": "junior",
    "junior": "junior",
    "jr": "junior",
    "mid": "mid",
    "midlevel": "mid",
    "senior": "senior",
    "sr": "senior",
    "staff": "staff",
    "principal": "staff",
    "lead": "staff",
}
_TECH_ROLE_TERMS = {
    "ai",
    "artificial",
    "data",
    "deep",
    "intelligence",
    "learning",
    "machine",
    "ml",
    "model",
    "research",
    "scientist",
}
_ROLE_NOUNS = {"developer", "engineer", "researcher", "scientist"}
_UNKNOWN_WORK_MODES = {"", "any", "flexible", "not specified", "unknown", "unspecified"}
_REMOTE_MODES = {"remote", "remote-first", "distributed"}
_ONSITE_MODES = {"hybrid", "in-office", "office", "on-site", "onsite"}


def apply_rules(job: Any, company: Any, target_profile: Any) -> RulesFilterResult:
    reasons: list[str] = []
    risks: list[str] = []
    score = 50

    title = str(_field(job, "title", "") or "")
    job_text = " ".join(
        str(value or "")
        for value in (
            title,
            _field(job, "description_text"),
            _field(job, "requirements_text"),
        )
    )
    role_status = _role_status(title, _target_titles(target_profile))
    skill_matches = _keyword_matches(_strings(_field(target_profile, "keywords")), job_text)
    strong_skills = bool(skill_matches) and len(skill_matches) >= min(
        2, len(_strings(_field(target_profile, "keywords"))) or 1
    )

    if role_status == "match":
        reasons.append("role_match")
        score += 30
    elif role_status == "adjacent":
        reasons.append("adjacent_role")
        risks.append("role_needs_review")
        score += 15
    else:
        risks.append("role_mismatch")
        score -= 30

    if skill_matches:
        reasons.append("skills_match")
        score += min(20, 6 * len(skill_matches))
    elif _strings(_field(target_profile, "keywords")):
        risks.append("skills_not_confirmed")
        score -= 5

    location_status = _location_status(
        str(_field(job, "location_text", "") or ""),
        str(_field(job, "remote_mode", "") or ""),
        _strings(_field(target_profile, "locations")),
    )
    if location_status == "mismatch":
        risks.append("location_mismatch")
        score -= 40
        return _result("reject", score, reasons, risks)
    if location_status == "match":
        reasons.append("location_match")
        score += 5
    elif location_status == "unknown":
        risks.append("unknown_location")

    seniority_status = _seniority_status(
        str(_field(job, "seniority", "") or title),
        str(_field(target_profile, "level", "") or ""),
    )
    if seniority_status == "mismatch":
        risks.append("seniority_mismatch")
        score -= 10
    elif seniority_status == "match":
        reasons.append("seniority_match")
        score += 5

    work_mode_status = _work_mode_status(
        str(_field(job, "remote_mode", "") or ""),
        str(_field(target_profile, "work_mode", "") or ""),
    )
    if work_mode_status == "unknown":
        risks.append("unknown_work_mode")
        score -= 5
    elif work_mode_status == "mismatch":
        risks.append("work_mode_mismatch")
        score -= 10
    elif work_mode_status == "match":
        reasons.append("work_mode_match")
        score += 5

    if _stage_mismatch(company, target_profile):
        risks.append("company_stage_mismatch")
        score -= 5

    if "role_mismatch" in risks and not strong_skills:
        return _result("reject", score, reasons, risks)

    return _result("soft_pass" if risks else "pass", score, reasons, risks)


def review_candidate_job(
    conn: sqlite3.Connection,
    job_id: int,
    target_profile_id: int,
    llm_client: FitGateClient,
) -> int:
    job_row, company_row = _job_and_company(conn, job_id)
    profile_row = _target_profile_row(conn, target_profile_id)
    profile_version = current_profile_version(conn, target_profile_id)
    job = _job_from_row(job_row)
    company = _company_from_row(company_row)
    target_profile = _target_profile_from_row(conn, profile_row)

    rules_result = apply_rules(job, company, target_profile)
    rules_result_id = _insert_rules_filter_result(
        conn, job_id, target_profile_id, rules_result
    )

    if rules_result.outcome == "reject":
        return _insert_fit_review(
            conn,
            job_id=job_id,
            target_profile_id=target_profile_id,
            rules_filter_result_id=rules_result_id,
            llm_request_id=None,
            fit_score=rules_result.score,
            label="Filtered out",
            reasons=rules_result.reasons,
            risks=rules_result.risks,
            recommendation="Filtered by rules before LLM review.",
            profile_version=profile_version,
        )

    payload = FitGatePayload(
        job=_public_job_payload(job_id, job_row),
        company=_public_company_payload(company_row),
        target_profile=_target_profile_payload(profile_row, profile_version),
        rules_result={
            "outcome": rules_result.outcome,
            "score": rules_result.score,
            "reasons": list(rules_result.reasons),
            "risks": list(rules_result.risks),
        },
    )
    request = LLMRequest(
        feature="fit_gate",
        schema_version=getattr(llm_client, "schema_version", "fit_gate.v1"),
        model=getattr(llm_client, "model", "unknown"),
        provider=getattr(llm_client, "provider", "openrouter"),
        input_reference=f"job:{job_id}|profile:{target_profile_id}|v:{profile_version}",
        private_prompt=f"fit_gate:{job_id}:{target_profile_id}:{profile_version}",
    )
    raw_response: Any = {}
    try:
        raw_response = llm_client.review_fit(payload)
        response = FitGateResponse.model_validate(raw_response)
    except Exception as exc:
        record_llm_request(
            conn,
            request,
            status="failed",
            response_payload=raw_response if isinstance(raw_response, dict) else {},
            error="response validation failed"
            if isinstance(exc, ValidationError)
            else str(exc),
        )
        raise

    llm_request_id = record_llm_request(
        conn,
        request,
        status="succeeded",
        response_payload=response.model_dump(),
    )

    return _insert_fit_review(
        conn,
        job_id=job_id,
        target_profile_id=target_profile_id,
        rules_filter_result_id=rules_result_id,
        llm_request_id=llm_request_id,
        fit_score=response.fit_score,
        label=response.label,
        reasons=tuple(response.reasons),
        risks=tuple(response.risks),
        recommendation=response.recommendation,
        profile_version=profile_version,
    )


def review_jobs_for_profile(
    conn: sqlite3.Connection,
    target_profile_id: int,
    llm_client: FitGateClient,
) -> list[int]:
    return [
        review_candidate_job(conn, int(row["id"]), target_profile_id, llm_client)
        for row in _candidate_job_rows(conn, target_profile_id)
    ]


def review_jobs_for_profile_resilient(
    conn: sqlite3.Connection,
    target_profile_id: int,
    llm_client: FitGateClient,
) -> ProfileReviewBatchResult:
    review_ids: list[int] = []
    failures = 0
    for row in _candidate_job_rows(conn, target_profile_id):
        try:
            review_ids.append(
                review_candidate_job(conn, int(row["id"]), target_profile_id, llm_client)
            )
        except Exception:
            failures += 1
    return ProfileReviewBatchResult(review_ids=review_ids, failures=failures)


def rules_preview_jobs(
    conn: sqlite3.Connection,
    target_profile_id: int,
    *,
    limit: int = 12,
    candidate_limit: int = 500,
) -> list[RulesPreviewJob]:
    profile_row = _target_profile_row(conn, target_profile_id)
    target_profile = _target_profile_from_row(conn, profile_row)
    previews: list[RulesPreviewJob] = []
    for row in _rules_preview_candidate_rows(
        conn, target_profile_id, candidate_limit=candidate_limit
    ):
        rules_result = apply_rules(
            _job_from_row(row),
            Company(
                name=str(row["company_name"]),
                categories=tuple(_json_list(row["categories_json"])),
                tags=tuple(_json_list(row["categories_json"])),
                stage=row["company_stage"],
            ),
            target_profile,
        )
        if rules_result.outcome == "reject":
            continue
        previews.append(
            RulesPreviewJob(
                job_id=int(row["id"]),
                title=row["title"],
                company_name=str(row["company_name"]),
                location_text=row["location_text"],
                remote_mode=row["remote_mode"],
                score=rules_result.score,
                outcome=rules_result.outcome,
                reasons=rules_result.reasons,
                risks=rules_result.risks,
            )
        )
    return sorted(
        previews,
        key=lambda preview: (-preview.score, preview.company_name, preview.title),
    )[:limit]


def _rules_preview_candidate_rows(
    conn: sqlite3.Connection,
    target_profile_id: int,
    *,
    candidate_limit: int,
) -> list[sqlite3.Row]:
    profile_version = current_profile_version(conn, target_profile_id)
    return conn.execute(
        """
        SELECT
          jobs.*,
          companies.name AS company_name,
          companies.categories_json,
          companies.stage AS company_stage
        FROM jobs
        JOIN companies ON companies.id = jobs.company_id
        WHERE jobs.status = 'open'
          AND NOT EXISTS (
            SELECT 1
            FROM fit_reviews
            WHERE fit_reviews.job_id = jobs.id
              AND fit_reviews.target_profile_id = ?
              AND fit_reviews.profile_version = ?
          )
        ORDER BY jobs.last_seen_at DESC, jobs.id DESC
        LIMIT ?
        """,
        (target_profile_id, profile_version, candidate_limit),
    ).fetchall()


def _candidate_job_rows(
    conn: sqlite3.Connection, target_profile_id: int
) -> list[sqlite3.Row]:
    profile_version = current_profile_version(conn, target_profile_id)
    return conn.execute(
        """
        SELECT jobs.id
        FROM jobs
        JOIN companies ON companies.id = jobs.company_id
        WHERE jobs.status = 'open'
          AND NOT EXISTS (
            SELECT 1
            FROM fit_reviews
            WHERE fit_reviews.job_id = jobs.id
              AND fit_reviews.target_profile_id = ?
              AND fit_reviews.profile_version = ?
          )
        ORDER BY companies.name, jobs.title
        """,
        (target_profile_id, profile_version),
    ).fetchall()


def visible_company_results(
    conn: sqlite3.Connection,
    target_profile_id: int,
) -> list[CompanyResult]:
    profile_version = current_profile_version(conn, target_profile_id)
    rows = conn.execute(
        """
        SELECT
          fit_reviews.id AS review_id,
          fit_reviews.fit_score,
          fit_reviews.label,
          fit_reviews.reasons_json,
          fit_reviews.risks_json,
          fit_reviews.recommendation,
          job_decisions.decision,
          COALESCE(job_decisions.notes, '') AS decision_notes,
          jobs.id AS job_id,
          jobs.title,
          companies.id AS company_id,
          companies.name AS company_name
        FROM fit_reviews
        JOIN jobs ON jobs.id = fit_reviews.job_id
        JOIN companies ON companies.id = jobs.company_id
        LEFT JOIN job_decisions
          ON job_decisions.job_id = jobs.id
         AND job_decisions.target_profile_id = ?
        WHERE fit_reviews.target_profile_id = ?
          AND fit_reviews.profile_version = ?
          AND jobs.status = 'open'
          AND fit_reviews.id IN (
            SELECT MAX(id)
            FROM fit_reviews
            WHERE target_profile_id = ? AND profile_version = ?
            GROUP BY job_id
          )
        ORDER BY companies.name, fit_reviews.fit_score DESC, jobs.title
        """,
        (
            target_profile_id,
            target_profile_id,
            profile_version,
            target_profile_id,
            profile_version,
        ),
    ).fetchall()

    companies: dict[int, dict[str, Any]] = {}
    for row in rows:
        bucket = companies.setdefault(
            int(row["company_id"]),
            {
                "name": row["company_name"],
                "visible": [],
                "mismatch": [],
                "hidden": [],
                "filtered": 0,
            },
        )
        job_result = JobFitResult(
            job_id=int(row["job_id"]),
            title=row["title"],
            fit_score=int(row["fit_score"]),
            label=row["label"],
            reasons=tuple(json.loads(row["reasons_json"] or "[]")),
            risks=tuple(json.loads(row["risks_json"] or "[]")),
            recommendation=row["recommendation"],
            decision=row["decision"],
            notes=row["decision_notes"],
        )
        if row["decision"] == "hidden":
            bucket["hidden"].append(job_result)
        elif row["label"] in {"Strong fit", "Possible fit"}:
            bucket["visible"].append(job_result)
        elif row["label"] == "Mismatch risk":
            bucket["mismatch"].append(job_result)
        elif row["label"] == "Filtered out":
            bucket["filtered"] += 1

    return [
        CompanyResult(
            company_id=company_id,
            name=str(bucket["name"]),
            visible_jobs=list(bucket["visible"]),
            mismatch_risk_jobs=list(bucket["mismatch"]),
            hidden_jobs=list(bucket["hidden"]),
            filtered_out_count=int(bucket["filtered"]),
        )
        for company_id, bucket in companies.items()
    ]


def _result(
    outcome: RulesOutcome, score: int, reasons: list[str], risks: list[str]
) -> RulesFilterResult:
    return RulesFilterResult(
        outcome=outcome,
        score=max(0, min(100, score)),
        reasons=tuple(dict.fromkeys(reasons)),
        risks=tuple(dict.fromkeys(risks)),
    )


def _job_and_company(
    conn: sqlite3.Connection, job_id: int
) -> tuple[sqlite3.Row, Mapping[str, Any]]:
    row = conn.execute(
        """
        SELECT
          jobs.*,
          companies.id AS company_id,
          companies.name AS company_name,
          companies.categories_json,
          companies.stage AS company_stage
        FROM jobs
        JOIN companies ON companies.id = jobs.company_id
        WHERE jobs.id = ?
        """,
        (job_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"job_id not found: {job_id}")

    company_row = {
        "id": row["company_id"],
        "name": row["company_name"],
        "categories_json": row["categories_json"],
        "stage": row["company_stage"],
    }
    return row, company_row


def _target_profile_row(conn: sqlite3.Connection, target_profile_id: int) -> sqlite3.Row:
    row = conn.execute(
        "SELECT * FROM target_profiles WHERE id = ?",
        (target_profile_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"target_profile_id not found: {target_profile_id}")
    return row


def _job_from_row(row: sqlite3.Row) -> Job:
    return Job(
        title=row["title"],
        location_text=row["location_text"],
        remote_mode=row["remote_mode"],
        seniority=row["seniority"],
        description_text=row["description_text"],
        requirements_text=row["requirements_text"],
    )


def _company_from_row(row: Mapping[str, Any]) -> Company:
    categories = tuple(_json_list(row.get("categories_json")))
    return Company(
        name=str(row["name"]),
        categories=categories,
        tags=categories,
        stage=row.get("stage"),
    )


def _target_profile_from_row(conn: sqlite3.Connection, row: sqlite3.Row) -> TargetProfile:
    titles = tuple(_json_list(row["desired_titles_json"]))
    levels = _json_list(row["levels_json"])
    locations = tuple(_json_list(row["locations_json"]))
    remote_modes = _json_list(row["remote_modes_json"])
    stages = _json_list(row["company_stages_json"])
    keywords = tuple(_resume_keywords(conn, row["resume_asset_id"]) or titles)
    return TargetProfile(
        role=titles[0] if titles else None,
        titles=titles,
        level=levels[0] if levels else None,
        locations=locations,
        work_mode=remote_modes[0] if remote_modes else None,
        company_stage=stages[0] if stages else None,
        keywords=keywords,
    )


def _insert_rules_filter_result(
    conn: StoreConnection,
    job_id: int,
    target_profile_id: int,
    result: RulesFilterResult,
) -> int:
    cursor = conn.execute(
        """
        INSERT INTO rules_filter_results (
          job_id,
          target_profile_id,
          outcome,
          score,
          reasons_json
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            job_id,
            target_profile_id,
            result.outcome,
            result.score,
            json.dumps(list(result.reasons), sort_keys=True),
        ),
    )
    conn.commit()
    return int(cursor.lastrowid)


def _insert_fit_review(
    conn: StoreConnection,
    *,
    job_id: int,
    target_profile_id: int,
    rules_filter_result_id: int,
    llm_request_id: int | None,
    fit_score: int,
    label: str,
    reasons: tuple[str, ...],
    risks: tuple[str, ...],
    recommendation: str,
    profile_version: int,
) -> int:
    cursor = conn.execute(
        """
        INSERT INTO fit_reviews (
          job_id,
          target_profile_id,
          rules_filter_result_id,
          llm_request_id,
          fit_score,
          label,
          reasons_json,
          risks_json,
          recommendation,
          profile_version
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            job_id,
            target_profile_id,
            rules_filter_result_id,
            llm_request_id,
            fit_score,
            label,
            json.dumps(list(reasons), sort_keys=True),
            json.dumps(list(risks), sort_keys=True),
            recommendation,
            profile_version,
        ),
    )
    conn.commit()
    return int(cursor.lastrowid)


def _public_job_payload(job_id: int, row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": job_id,
        "title": row["title"],
        "department": row["department"],
        "location_text": row["location_text"],
        "remote_mode": row["remote_mode"],
        "employment_type": row["employment_type"],
        "seniority": row["seniority"],
        "description_text": row["description_text"],
        "requirements_text": row["requirements_text"],
    }


def _public_company_payload(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "name": row["name"],
        "categories": _json_list(row.get("categories_json")),
        "stage": row.get("stage"),
    }


def _target_profile_payload(row: sqlite3.Row, profile_version: int) -> dict[str, Any]:
    return {
        "id": row["id"],
        "version": profile_version,
        "desired_titles": _json_list(row["desired_titles_json"]),
        "levels": _json_list(row["levels_json"]),
        "locations": _json_list(row["locations_json"]),
        "remote_modes": _json_list(row["remote_modes_json"]),
        "company_stages": _json_list(row["company_stages_json"]),
    }


def _json_list(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        parsed = raw
    else:
        parsed = json.loads(str(raw))
    if not isinstance(parsed, list):
        return []
    return [str(item) for item in parsed if str(item).strip()]


def _resume_keywords(conn: sqlite3.Connection, resume_asset_id: int | None) -> list[str]:
    if resume_asset_id is None:
        return []
    rows = conn.execute(
        """
        SELECT DISTINCT resume_keywords.keyword
        FROM resume_keywords
        JOIN resume_parse_runs
          ON resume_parse_runs.id = resume_keywords.parse_run_id
        WHERE resume_parse_runs.resume_asset_id = ?
        ORDER BY resume_keywords.weight DESC, resume_keywords.keyword
        """,
        (resume_asset_id,),
    ).fetchall()
    return [row["keyword"] for row in rows]


def _field(source: Any, name: str, default: Any = None) -> Any:
    if source is None:
        return default
    if isinstance(source, Mapping):
        return source.get(name, default)
    return getattr(source, name, default)


def _strings(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,) if value.strip() else ()
    try:
        return tuple(str(item) for item in value if str(item).strip())
    except TypeError:
        return (str(value),) if str(value).strip() else ()


def _target_titles(target_profile: Any) -> tuple[str, ...]:
    titles = list(_strings(_field(target_profile, "titles")))
    role = _field(target_profile, "role")
    if role:
        titles.insert(0, str(role))
    return tuple(dict.fromkeys(titles))


def _tokens(text: str) -> set[str]:
    return set(_WORD_RE.findall(text.lower()))


def _normalized(text: str) -> str:
    return " ".join(_WORD_RE.findall(text.lower()))


_NORMALIZED_REMOTE_MODES = {_normalized(mode) for mode in _REMOTE_MODES}
_NORMALIZED_ONSITE_MODES = {_normalized(mode) for mode in _ONSITE_MODES}


def _role_status(title: str, target_titles: tuple[str, ...]) -> str:
    title_tokens = _tokens(title)
    for target in target_titles:
        target_tokens = _tokens(target) - set(_SENIORITY)
        if target_tokens and target_tokens <= title_tokens:
            return "match"

    target_tokens = set().union(*(_tokens(target) for target in target_titles)) if target_titles else set()
    if (
        title_tokens & _TECH_ROLE_TERMS
        and target_tokens & _TECH_ROLE_TERMS
        and title_tokens & _ROLE_NOUNS
    ):
        return "adjacent"
    return "mismatch"


def _keyword_matches(keywords: tuple[str, ...], text: str) -> tuple[str, ...]:
    normalized_text = _normalized(text)
    text_tokens = _tokens(text)
    matches = []
    for keyword in keywords:
        normalized_keyword = _normalized(keyword)
        if not normalized_keyword:
            continue
        keyword_tokens = set(normalized_keyword.split())
        if normalized_keyword in normalized_text or keyword_tokens <= text_tokens:
            matches.append(normalized_keyword)
    return tuple(dict.fromkeys(matches))


def _location_status(
    job_location: str, remote_mode: str, target_locations: tuple[str, ...]
) -> str:
    if not target_locations:
        return "unknown"
    if not job_location.strip():
        return "unknown"
    if _is_remote(job_location) or _is_remote(remote_mode):
        return "match" if _location_matches(job_location, target_locations) else "unknown"
    if _location_matches(job_location, target_locations):
        return "match"
    return "mismatch"


def _location_matches(job_location: str, target_locations: tuple[str, ...]) -> bool:
    job_aliases = _location_aliases(job_location)
    for target in target_locations:
        if job_aliases & _location_aliases(target):
            return True
    return False


def _location_aliases(location: str) -> set[str]:
    normalized = _normalized(location)
    aliases = {normalized} if normalized else set()
    tokens = _tokens(location)
    aliases.update(tokens)
    if {"new", "york"} <= tokens:
        aliases.update({"ny", "nyc", "new york", "new york city"})
    if {"san", "francisco"} <= tokens:
        aliases.update({"sf", "bay area", "san francisco"})
    return {alias for alias in aliases if alias}


def _is_remote(value: str) -> bool:
    return any(mode in _normalized(value) for mode in ("remote", "distributed", "anywhere"))


def _seniority_status(job_seniority: str, target_level: str) -> str:
    job_level = _seniority_level(job_seniority)
    target = _seniority_level(target_level)
    if not job_level or not target:
        return "unknown"
    return "match" if job_level == target else "mismatch"


def _seniority_level(value: str) -> str | None:
    tokens = _tokens(value)
    for token in tokens:
        if token in _SENIORITY:
            return _SENIORITY[token]
    return None


def _work_mode_status(job_mode: str, target_mode: str) -> str:
    target = _normalized(target_mode)
    if not target:
        return "unknown"
    job = _normalized(job_mode)
    if job in _UNKNOWN_WORK_MODES:
        return "unknown"
    if target == job:
        return "match"
    if target in _NORMALIZED_REMOTE_MODES and job in _NORMALIZED_REMOTE_MODES:
        return "match"
    if target in _NORMALIZED_ONSITE_MODES and job in _NORMALIZED_ONSITE_MODES:
        return "match"
    return "mismatch"


def _stage_mismatch(company: Any, target_profile: Any) -> bool:
    target_stage = _normalized(str(_field(target_profile, "company_stage", "") or ""))
    company_stage = _normalized(str(_field(company, "stage", "") or ""))
    return bool(target_stage and company_stage and target_stage != company_stage)
