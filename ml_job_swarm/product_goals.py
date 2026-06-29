from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, Literal, Mapping, Sequence

from ml_job_swarm.adapters import public_ats_registry
from ml_job_swarm.source_policy import classify_source_url
from ml_job_swarm.store import SCHEMA_SQL


ProductSourceStatus = Literal["supported", "unsupported", "blocked", "needs_review"]
PRODUCT_SOURCE_STATUSES: set[ProductSourceStatus] = {
    "supported",
    "unsupported",
    "blocked",
    "needs_review",
}

_FORBIDDEN_EXTERNAL_SUBMIT_RE = re.compile(
    r"\b(?:submit_application|auto_submit_application|auto_submit|external_submit)\s*\("
)
_SKIPPED_DIRS = {".git", ".mypy_cache", ".pytest_cache", ".ruff_cache", ".venv", "__pycache__"}
_COMPANY_SUFFIXES = {
    "co",
    "company",
    "corp",
    "corporation",
    "inc",
    "incorporated",
    "llc",
    "ltd",
}


@dataclass(frozen=True)
class SeedSourceAuditRecord:
    company_name: str
    url: str
    source_type: str
    status: ProductSourceStatus
    reason: str
    policy_mode: str
    normalized_url: str | None
    next_action: str


def audit_seed_sources(
    companies: Sequence[Mapping[str, object]],
) -> list[SeedSourceAuditRecord]:
    supported_source_types = public_ats_registry().source_types()
    records: list[SeedSourceAuditRecord] = []
    for company in companies:
        company_name = str(company.get("name") or "").strip()
        primary_url = _string_value(company.get("careers_url"))
        primary_type = _string_value(company.get("ats_type")) or "careers"
        if primary_url:
            records.append(
                _audit_source(
                    company_name=company_name,
                    url=primary_url,
                    source_type=primary_type,
                    supported_source_types=supported_source_types,
                )
            )
        for extra_source in _iter_extra_sources(company):
            url = _string_value(extra_source.get("url"))
            if not url:
                continue
            source_type = _string_value(extra_source.get("source_type")) or primary_type
            records.append(
                _audit_source(
                    company_name=company_name,
                    url=url,
                    source_type=source_type,
                    supported_source_types=supported_source_types,
                )
            )
    return records


def evaluate_product_metrics(metrics: Mapping[str, object]) -> list[str]:
    violations: list[str] = []

    source_refresh = _metric_section(metrics, "source_refresh")
    success_rate = _metric_float(source_refresh.get("supported_source_success_rate"))
    target_success_rate = _metric_float(
        source_refresh.get("target_success_rate"),
        default=0.9,
    )
    if success_rate is not None and success_rate < target_success_rate:
        violations.append(
            "Supported source success rate "
            f"{success_rate:.4f} is below target {target_success_rate:.4f}."
        )

    application_packets = _metric_section(metrics, "application_packets")
    prepared_packet_rate = _metric_float(application_packets.get("prepared_packet_rate"))
    target_prepared_packet_rate = _metric_float(
        application_packets.get("target_prepared_packet_rate"),
        default=0.95,
    )
    if (
        prepared_packet_rate is not None
        and prepared_packet_rate < target_prepared_packet_rate
    ):
        violations.append(
            "Prepared packet rate "
            f"{prepared_packet_rate:.4f} is below target {target_prepared_packet_rate:.4f}."
        )

    manual_submission = _metric_section(metrics, "manual_submission")
    external_submit_paths = _metric_int(manual_submission.get("external_submit_paths"))
    target_external_submit_paths = _metric_int(
        manual_submission.get("target_external_submit_paths"),
        default=0,
    )
    if (
        external_submit_paths is not None
        and external_submit_paths != target_external_submit_paths
    ):
        violations.append(
            "Manual submission has "
            f"{external_submit_paths} external submit path(s); target is "
            f"{target_external_submit_paths}."
        )

    catalog = _metric_section(metrics, "catalog")
    jobs_seen = _metric_int(catalog.get("jobs_seen"))
    target_jobs_seen_min = _metric_int(catalog.get("target_jobs_seen_min"), default=1)
    if jobs_seen is not None and jobs_seen < target_jobs_seen_min:
        violations.append(
            f"Catalog jobs_seen {jobs_seen} is below target minimum {target_jobs_seen_min}."
        )

    first_run = _metric_section(metrics, "first_run")
    elapsed_seconds = _metric_float(first_run.get("elapsed_seconds"))
    if elapsed_seconds is not None and not bool(first_run.get("browser_e2e_ok")):
        violations.append(
            "First-run browser E2E check failed while elapsed_seconds was recorded."
        )

    return violations


def build_live_smoke_product_metrics(
    *,
    refresh_summary: Mapping[str, int],
    packet_prepared: bool,
    saved_jobs_count: int,
    elapsed_seconds: float | None = None,
    source_failures: Sequence[Mapping[str, object]] | None = None,
    external_submit_paths: int = 0,
) -> dict[str, object]:
    sources_attempted = int(refresh_summary.get("sources_attempted", 0) or 0)
    sources_succeeded = int(refresh_summary.get("sources_succeeded", 0) or 0)
    jobs_seen = int(refresh_summary.get("jobs_seen", 0) or 0)
    failures = list(source_failures or [])
    success_rate = sources_succeeded / sources_attempted if sources_attempted else 0.0
    visible_failure_reason_count = sum(
        1
        for failure in failures
        if _string_value(failure.get("reason") or failure.get("event_type"))
    )
    missing_failure_reason_count = max(
        (sources_attempted - sources_succeeded) - visible_failure_reason_count,
        0,
    )
    has_visible_failure_reasons = missing_failure_reason_count == 0 and all(
        bool(_string_value(failure.get("reason") or failure.get("event_type")))
        for failure in failures
    )

    return {
        "first_run": {
            "browser_e2e_ok": jobs_seen > 0 and packet_prepared,
            "elapsed_seconds": elapsed_seconds,
            "target_seconds": 600,
        },
        "source_refresh": {
            "sources_attempted": sources_attempted,
            "sources_succeeded": sources_succeeded,
            "supported_source_success_rate": round(success_rate, 4),
            "target_success_rate": 0.9,
            "sources_have_visible_failure_reasons": has_visible_failure_reasons,
            "visible_failure_reason_count": visible_failure_reason_count,
            "missing_failure_reason_count": missing_failure_reason_count,
        },
        "catalog": {
            "jobs_seen": jobs_seen,
            "target_jobs_seen_min": 1,
        },
        "saved_jobs": {
            "saved_jobs_count": int(saved_jobs_count),
            "target_saved_jobs_min": 1,
        },
        "application_packets": {
            "packet_prepared": packet_prepared,
            "prepared_packet_rate": 1.0 if packet_prepared else 0.0,
            "target_prepared_packet_rate": 0.95,
        },
        "manual_submission": {
            "external_submit_paths": int(external_submit_paths),
            "target_external_submit_paths": 0,
        },
    }


def next_action_coverage(
    states: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    total = len(states)
    missing_states = [
        str(state.get("state") or "unknown")
        for state in states
        if not _string_value(state.get("next_action"))
    ]
    covered = total - len(missing_states)
    return {
        "states_checked": total,
        "coverage_rate": covered / total if total else 1.0,
        "missing_states": missing_states,
    }


def manual_submit_boundary_report(root: Path) -> dict[str, object]:
    root = Path(root)
    external_submit_paths: list[str] = []
    for file_path in _iter_scannable_files(root):
        text = file_path.read_text(encoding="utf-8", errors="ignore")
        if _FORBIDDEN_EXTERNAL_SUBMIT_RE.search(text):
            external_submit_paths.append(file_path.relative_to(root).as_posix())

    return {
        "external_submit_paths": external_submit_paths,
        "manual_statuses": _application_packet_statuses(),
    }


def local_referral_alias_match_report(
    *,
    companies: Sequence[Mapping[str, object]],
    contacts: Sequence[Mapping[str, object]],
    jobs: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    company_aliases: dict[str, int] = {}
    for company in companies:
        company_id = int(company["id"])
        names = [_string_value(company.get("name"))]
        names.extend(str(alias) for alias in company.get("aliases") or [])
        for name in names:
            normalized = _normalize_company_name(name)
            if normalized:
                company_aliases[normalized] = company_id

    contact_counts: dict[int, int] = {}
    for contact in contacts:
        company_id = int(contact["company_id"])
        contact_counts[company_id] = contact_counts.get(company_id, 0) + 1

    suggestions: list[dict[str, int]] = []
    true_positive = 0
    false_positive = 0
    unlabeled_suggestion_count = 0
    for job in jobs:
        company_id = company_aliases.get(_normalize_company_name(job.get("company_name")))
        if company_id is None:
            continue
        contact_count = contact_counts.get(company_id, 0)
        if contact_count <= 0:
            continue
        suggestions.append(
            {
                "job_id": int(job["id"]),
                "company_id": company_id,
                "contact_count": contact_count,
            }
        )
        expected_company_id = job.get("expected_company_id")
        if expected_company_id is None:
            unlabeled_suggestion_count += 1
        elif int(expected_company_id) == company_id:
            true_positive += 1
        else:
            false_positive += 1

    denominator = true_positive + false_positive
    return {
        "precision": true_positive / denominator if denominator else None,
        "labeled_suggestion_count": denominator,
        "unlabeled_suggestion_count": unlabeled_suggestion_count,
        "suggestions": suggestions,
        "outbound_action_count": 0,
    }


def catalog_quality_metrics(
    jobs: Sequence[Mapping[str, object]],
    *,
    now: datetime | None = None,
    closed_hidden_after_hours: int = 48,
) -> dict[str, object]:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    total = len(jobs)
    canonical_urls = [_canonical_job_url(job) for job in jobs]
    duplicate_count = total - len({url for url in canonical_urls if url})
    stale_cutoff = now - timedelta(hours=closed_hidden_after_hours)
    stale_closed_visible_count = sum(
        1
        for job in jobs
        if _is_closed_visible_past_cutoff(job, stale_cutoff=stale_cutoff)
    )

    return {
        "job_count": total,
        "duplicate_count": duplicate_count,
        "duplicate_rate": duplicate_count / total if total else 0.0,
        "target_duplicate_rate_max": 0.02,
        "stale_closed_visible_count": stale_closed_visible_count,
        "closed_hidden_after_hours": closed_hidden_after_hours,
    }


def _audit_source(
    *,
    company_name: str,
    url: str,
    source_type: str,
    supported_source_types: set[str],
) -> SeedSourceAuditRecord:
    policy = classify_source_url(url)
    if policy.mode == "blocked":
        status: ProductSourceStatus = "blocked"
        next_action = "Replace with an approved employer or ATS source."
    elif policy.mode == "manual_link":
        status = "needs_review"
        next_action = "Review the source manually before enabling refresh."
    elif source_type not in supported_source_types:
        status = "unsupported"
        next_action = "Add an adapter or change the configured source type."
    else:
        status = "supported"
        next_action = "Refresh the source."
    return SeedSourceAuditRecord(
        company_name=company_name,
        url=url,
        source_type=source_type,
        status=status,
        reason=policy.reason,
        policy_mode=policy.mode,
        normalized_url=policy.normalized_url,
        next_action=next_action,
    )


def _iter_extra_sources(
    company: Mapping[str, object],
) -> Iterable[Mapping[str, object]]:
    extra_sources = company.get("extra_sources") or []
    if isinstance(extra_sources, list):
        for extra_source in extra_sources:
            if isinstance(extra_source, Mapping):
                yield extra_source


def _iter_scannable_files(root: Path) -> Iterable[Path]:
    if root.is_file():
        yield root
        return
    for file_path in root.rglob("*"):
        if any(part in _SKIPPED_DIRS for part in file_path.parts):
            continue
        if file_path.suffix not in {".py", ".html"}:
            continue
        yield file_path


def _application_packet_statuses() -> list[str]:
    match = re.search(r"status IN \(([^)]+)\)", SCHEMA_SQL)
    if not match:
        return []
    return [status.strip().strip("'\"") for status in match.group(1).split(",")]


def _canonical_job_url(job: Mapping[str, object]) -> str:
    return _string_value(
        job.get("canonical_url")
        or job.get("url")
        or job.get("apply_url")
        or job.get("external_id")
    )


def _is_closed_visible_past_cutoff(
    job: Mapping[str, object],
    *,
    stale_cutoff: datetime,
) -> bool:
    if bool(job.get("hidden")) or job.get("visible") is False or job.get("decision") == "hidden":
        return False
    closed_at = _parse_datetime(job.get("closed_at"))
    if closed_at is None:
        return False
    return closed_at <= stale_cutoff


def _parse_datetime(value: object) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _normalize_company_name(value: object) -> str:
    text = re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold()).strip()
    tokens = [token for token in text.split() if token not in _COMPANY_SUFFIXES]
    return " ".join(tokens)


def _string_value(value: object) -> str:
    return str(value or "").strip()


def _metric_section(metrics: Mapping[str, object], key: str) -> Mapping[str, object]:
    section = metrics.get(key)
    if isinstance(section, Mapping):
        return section
    return {}


def _metric_float(value: object, *, default: float | None = None) -> float | None:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _metric_int(value: object, *, default: int | None = None) -> int | None:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
