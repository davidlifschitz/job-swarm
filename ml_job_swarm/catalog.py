from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from ml_job_swarm.db.connection import StoreConnection, backend_kind_from_conn
from ml_job_swarm.db.dialect import insert_ignore_sql
from ml_job_swarm.source_policy import classify_source_url


@dataclass(frozen=True)
class SeedSource:
    url: str
    source_type: str


@dataclass(frozen=True)
class SeedCompany:
    name: str
    aliases: list[str]
    tags: list[str]
    stage: str
    priority_tier: int
    careers_url: str
    ats_type: str
    reviewed_at: str
    extra_sources: list[SeedSource]


def load_seed_companies(path: Path) -> list[SeedCompany]:
    raw_companies = json.loads(path.read_text())
    if not isinstance(raw_companies, list):
        raise ValueError("Seed catalog must be a JSON list")

    companies = [_parse_seed_company(item) for item in raw_companies]
    names = [_normalize_name(company.name) for company in companies]
    if len(names) != len(set(names)):
        raise ValueError("Seed catalog contains duplicate company names")
    return companies


def import_seed_companies(conn: StoreConnection, path: Path) -> int:
    companies = load_seed_companies(path)
    imported = 0

    for company in companies:
        reviewed_sources = _reviewed_seed_sources(company)
        primary_source = reviewed_sources[0]

        company_columns = [
            "name",
            "normalized_name",
            "aliases_json",
            "categories_json",
            "stage",
            "priority_tier",
            "careers_url",
            "ats_type",
            "source_quality",
        ]
        cursor = conn.execute(
            insert_ignore_sql(
                "companies",
                ["normalized_name"],
                company_columns,
                backend_kind_from_conn(conn),
            ),
            (
                company.name,
                _normalize_name(company.name),
                json.dumps(company.aliases, sort_keys=True),
                json.dumps(company.tags, sort_keys=True),
                company.stage,
                company.priority_tier,
                primary_source[0],
                company.ats_type,
                "reviewed",
            ),
        )
        if cursor.rowcount:
            imported += 1
        conn.execute(
            """
            UPDATE companies
            SET name = ?,
                aliases_json = ?,
                categories_json = ?,
                stage = ?,
                priority_tier = ?,
                careers_url = ?,
                ats_type = ?,
                source_quality = 'reviewed',
                updated_at = CURRENT_TIMESTAMP
            WHERE normalized_name = ?
            """,
            (
                company.name,
                json.dumps(company.aliases, sort_keys=True),
                json.dumps(company.tags, sort_keys=True),
                company.stage,
                company.priority_tier,
                primary_source[0],
                company.ats_type,
                _normalize_name(company.name),
            ),
        )

        company_id = conn.execute(
            "SELECT id FROM companies WHERE normalized_name = ?",
            (_normalize_name(company.name),),
        ).fetchone()["id"]
        source_columns = [
            "company_id",
            "url",
            "source_type",
            "policy_mode",
            "review_status",
        ]
        for source_url, source_type, policy_mode in reviewed_sources:
            conn.execute(
                insert_ignore_sql(
                    "job_sources",
                    ["company_id", "url"],
                    source_columns,
                    backend_kind_from_conn(conn),
                ),
                (
                    company_id,
                    source_url,
                    source_type,
                    policy_mode,
                    "reviewed",
                ),
            )
            conn.execute(
                """
                UPDATE job_sources
                SET source_type = ?,
                    policy_mode = ?,
                    review_status = 'reviewed',
                    updated_at = CURRENT_TIMESTAMP
                WHERE company_id = ? AND url = ?
                """,
                (
                    source_type,
                    policy_mode,
                    company_id,
                    source_url,
                ),
            )

    conn.commit()
    return imported


def _reviewed_seed_sources(company: SeedCompany) -> list[tuple[str, str, str]]:
    reviewed_sources: list[tuple[str, str, str]] = []
    for source in [
        SeedSource(company.careers_url, company.ats_type),
        *company.extra_sources,
    ]:
        policy = classify_source_url(source.url)
        if policy.mode != "allowed" or policy.normalized_url is None:
            raise ValueError(f"Seed source rejected for {company.name}: {policy.reason}")
        reviewed_sources.append((policy.normalized_url, source.source_type, policy.mode))
    return reviewed_sources


def submit_company_source(
    conn: StoreConnection, company_name: str, source_url: str
) -> int:
    policy = classify_source_url(source_url)
    status = "pending" if policy.mode != "blocked" else "blocked"
    reason = (
        "manual_review_required"
        if policy.mode != "blocked"
        else f"blocked:{policy.reason}"
    )
    requested_url = policy.normalized_url or source_url.strip()

    cursor = conn.execute(
        """
        INSERT INTO company_source_review_queue (
          company_name,
          requested_url,
          reason,
          status
        )
        VALUES (?, ?, ?, ?)
        """,
        (company_name.strip(), requested_url, reason, status),
    )

    if policy.mode == "blocked":
        conn.execute(
            """
            INSERT INTO source_friction_events (event_type, url, details_json)
            VALUES (?, ?, ?)
            """,
            (
                "policy_blocked",
                requested_url,
                json.dumps({"reason": policy.reason}, sort_keys=True),
            ),
        )

    conn.commit()
    return int(cursor.lastrowid)


def review_company_source(
    conn: StoreConnection,
    queue_id: int,
    action: str,
    actor: str = "local-admin",
) -> dict[str, object]:
    if action not in {"approve", "reject"}:
        raise ValueError("Source review action must be approve or reject")

    row = conn.execute(
        """
        SELECT id, company_name, requested_url, reason, status, reviewed_by
        FROM company_source_review_queue
        WHERE id = ?
        """,
        (queue_id,),
    ).fetchone()
    if row is None:
        raise ValueError("Queued source not found")

    before_json = json.dumps({"status": row["status"]}, sort_keys=True)
    if action == "reject":
        if row["status"] == "approved":
            raise ValueError("Approved sources cannot be rejected")
        _mark_queue_reviewed(conn, queue_id, "rejected", actor)
        result = {"status": "rejected", "job_source_id": None}
    else:
        if row["status"] == "blocked":
            raise ValueError("Blocked sources cannot be approved")
        requested_url = str(row["requested_url"] or "")
        policy = classify_source_url(requested_url)
        if policy.mode != "allowed" or policy.normalized_url is None:
            raise ValueError("Source cannot be approved unless policy mode is allowed")
        company_id = _upsert_company_for_review(
            conn,
            str(row["company_name"]),
            policy.normalized_url,
        )
        job_source_id = _upsert_job_source_for_review(
            conn,
            company_id,
            policy.normalized_url,
            infer_source_type(policy.normalized_url),
            policy.mode,
        )
        _mark_queue_reviewed(conn, queue_id, "approved", actor)
        result = {"status": "approved", "job_source_id": job_source_id}

    after_json = json.dumps(result | {"reviewed_by": actor}, sort_keys=True)
    conn.execute(
        """
        INSERT INTO admin_audit_events (
          actor,
          action,
          target_type,
          target_id,
          before_json,
          after_json
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            actor,
            action,
            "company_source_review_queue",
            str(queue_id),
            before_json,
            after_json,
        ),
    )
    conn.commit()
    return result


def _mark_queue_reviewed(
    conn: StoreConnection, queue_id: int, status: str, actor: str
) -> None:
    conn.execute(
        """
        UPDATE company_source_review_queue
        SET status = ?,
            reviewed_at = CURRENT_TIMESTAMP,
            reviewed_by = ?
        WHERE id = ?
        """,
        (status, actor, queue_id),
    )


def _upsert_company_for_review(
    conn: StoreConnection, company_name: str, careers_url: str
) -> int:
    normalized_name = _normalize_name(company_name)
    conn.execute(
        insert_ignore_sql(
            "companies",
            ["normalized_name"],
            ["name", "normalized_name", "careers_url", "source_quality"],
            backend_kind_from_conn(conn),
        ),
        (company_name.strip(), normalized_name, careers_url, "reviewed"),
    )
    conn.execute(
        """
        UPDATE companies
        SET careers_url = COALESCE(careers_url, ?),
            source_quality = 'reviewed',
            updated_at = CURRENT_TIMESTAMP
        WHERE normalized_name = ?
        """,
        (careers_url, normalized_name),
    )
    return int(
        conn.execute(
            "SELECT id FROM companies WHERE normalized_name = ?",
            (normalized_name,),
        ).fetchone()["id"]
    )


def _upsert_job_source_for_review(
    conn: StoreConnection,
    company_id: int,
    source_url: str,
    source_type: str,
    policy_mode: str,
) -> int:
    conn.execute(
        insert_ignore_sql(
            "job_sources",
            ["company_id", "url"],
            ["company_id", "url", "source_type", "policy_mode", "review_status"],
            backend_kind_from_conn(conn),
        ),
        (company_id, source_url, source_type, policy_mode, "reviewed"),
    )
    conn.execute(
        """
        UPDATE job_sources
        SET policy_mode = ?,
            review_status = 'reviewed',
            updated_at = CURRENT_TIMESTAMP
        WHERE company_id = ? AND url = ?
        """,
        (policy_mode, company_id, source_url),
    )
    return int(
        conn.execute(
            "SELECT id FROM job_sources WHERE company_id = ? AND url = ?",
            (company_id, source_url),
        ).fetchone()["id"]
    )


def infer_source_type(source_url: str) -> str:
    host = (urlsplit(source_url).hostname or "").lower()
    if "greenhouse.io" in host:
        return "greenhouse"
    if "lever.co" in host:
        return "lever"
    if "ashbyhq.com" in host:
        return "ashby"
    if "myworkdayjobs.com" in host:
        return "workday"
    if "smartrecruiters.com" in host:
        return "smartrecruiters"
    if "workable.com" in host:
        return "workable"
    return "careers"


def _infer_source_type(source_url: str) -> str:
    return infer_source_type(source_url)


def _parse_seed_company(item: dict[str, Any]) -> SeedCompany:
    required = {
        "name",
        "aliases",
        "tags",
        "stage",
        "priority_tier",
        "careers_url",
        "ats_type",
        "reviewed_at",
    }
    missing = required - item.keys()
    if missing:
        raise ValueError(f"Seed company missing fields: {sorted(missing)}")

    return SeedCompany(
        name=str(item["name"]).strip(),
        aliases=[str(alias).strip() for alias in item["aliases"]],
        tags=[str(tag).strip() for tag in item["tags"]],
        stage=str(item["stage"]).strip(),
        priority_tier=int(item["priority_tier"]),
        careers_url=str(item["careers_url"]).strip(),
        ats_type=str(item["ats_type"]).strip(),
        reviewed_at=str(item["reviewed_at"]).strip(),
        extra_sources=_parse_extra_sources(item.get("extra_sources", [])),
    )


def _parse_extra_sources(raw_sources: Any) -> list[SeedSource]:
    if not isinstance(raw_sources, list):
        raise ValueError("Seed company extra_sources must be a list")

    parsed: list[SeedSource] = []
    for raw_source in raw_sources:
        if not isinstance(raw_source, dict):
            raise ValueError("Seed company extra_sources entries must be objects")
        missing = {"url", "source_type"} - raw_source.keys()
        if missing:
            raise ValueError(f"Seed extra source missing fields: {sorted(missing)}")
        parsed.append(
            SeedSource(
                url=str(raw_source["url"]).strip(),
                source_type=str(raw_source["source_type"]).strip(),
            )
        )
    return parsed


def _normalize_name(name: str) -> str:
    return " ".join(name.casefold().split())
