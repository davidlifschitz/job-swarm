from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Protocol

from ml_job_swarm.db.connection import StoreConnection
from ml_job_swarm.source_policy import classify_source_url


@dataclass(frozen=True)
class JobSource:
    id: int
    company_id: int
    url: str
    source_type: str
    policy_mode: str
    review_status: str


@dataclass(frozen=True)
class RawJob:
    external_id: str | None
    title: str
    department: str | None = None
    location_text: str | None = None
    remote_mode: str | None = None
    employment_type: str | None = None
    seniority: str | None = None
    description_text: str | None = None
    requirements_text: str | None = None
    apply_url: str | None = None
    source_url: str | None = None


class JobSourceAdapter(Protocol):
    def fetch_jobs(self, source: JobSource) -> list[RawJob]: ...


class RefreshError(Exception):
    def __init__(
        self,
        message: str,
        event_type: str = "manual_review_needed",
        *,
        status_code: int | None = None,
    ):
        super().__init__(message)
        self.event_type = event_type
        self.status_code = status_code


@dataclass(frozen=True)
class RefreshResult:
    source_id: int
    ingestion_run_id: int
    status: str
    jobs_seen: int = 0
    jobs_added: int = 0
    jobs_updated: int = 0
    jobs_closed: int = 0


@dataclass(frozen=True)
class RefreshSummary:
    sources_seen: int
    sources_attempted: int
    sources_succeeded: int
    sources_refreshed: int
    jobs_seen: int
    jobs_closed: int
    failures: int
    blocked: int
    suspicious_empty: int


class AdapterRegistry:
    def __init__(self, adapters: dict[str, JobSourceAdapter]):
        self._adapters = adapters

    def adapter_for(self, source_type: str) -> JobSourceAdapter:
        try:
            return self._adapters[source_type]
        except KeyError as exc:
            raise RefreshError(
                f"No adapter registered for source type: {source_type}",
                "manual_review_needed",
            ) from exc

    def source_types(self) -> set[str]:
        return set(self._adapters)


def refresh_source(
    conn: StoreConnection, source_id: int, adapter: JobSourceAdapter
) -> RefreshResult:
    source = _load_source(conn, source_id)
    run_id = _start_run(conn, source_count=1)

    policy = classify_source_url(source.url)
    if source.policy_mode != "allowed" or policy.mode == "blocked":
        _record_friction(
            conn,
            source=source,
            run_id=run_id,
            event_type="policy_blocked",
            url=source.url,
            details={"policy_mode": source.policy_mode, "reason": policy.reason},
        )
        _finish_run(conn, run_id, status="blocked")
        return RefreshResult(source.id, run_id, "blocked")

    try:
        raw_jobs = adapter.fetch_jobs(source)
    except RefreshError as exc:
        _record_friction(
            conn,
            source=source,
            run_id=run_id,
            event_type=exc.event_type,
            url=source.url,
            details=_failure_details(exc),
            status_code=exc.status_code,
        )
        _finish_run(conn, run_id, status="failed", error=str(exc))
        return RefreshResult(source.id, run_id, "failed")
    except Exception as exc:
        _record_friction(
            conn,
            source=source,
            run_id=run_id,
            event_type="manual_review_needed",
            url=source.url,
            details={"error": str(exc)},
        )
        _finish_run(conn, run_id, status="failed", error=str(exc))
        return RefreshResult(source.id, run_id, "failed")

    if not raw_jobs:
        _record_friction(
            conn,
            source=source,
            run_id=run_id,
            event_type="empty_suspicious",
            url=source.url,
            details=_empty_result_details(source),
        )
        _finish_run(conn, run_id, status="suspicious_empty")
        _mark_source_checked(conn, source.id)
        return RefreshResult(source.id, run_id, "suspicious_empty")

    jobs_added = 0
    jobs_updated = 0
    seen_job_ids: set[int] = set()
    try:
        for raw_job in raw_jobs:
            content_hash = _content_hash(raw_job)
            _insert_snapshot(conn, run_id, source, raw_job, content_hash)
            existing_id = _find_existing_job(
                conn, source.company_id, raw_job, content_hash
            )
            if existing_id is None:
                seen_job_ids.add(_insert_job(conn, source, raw_job, content_hash))
                jobs_added += 1
            else:
                _update_job(conn, existing_id, source, raw_job, content_hash)
                seen_job_ids.add(existing_id)
                jobs_updated += 1
        jobs_closed = _close_stale_jobs(conn, source, seen_job_ids)
    except Exception as exc:
        conn.rollback()
        _record_friction(
            conn,
            source=source,
            run_id=run_id,
            event_type="manual_review_needed",
            url=source.url,
            details={"error": str(exc), "stage": "job_processing"},
        )
        _finish_run(conn, run_id, status="failed", error=str(exc))
        return RefreshResult(source.id, run_id, "failed")

    _finish_run(
        conn,
        run_id,
        status="succeeded",
        jobs_seen=len(raw_jobs),
        jobs_added=jobs_added,
        jobs_updated=jobs_updated,
        jobs_closed=jobs_closed,
    )
    _mark_source_checked(conn, source.id)
    return RefreshResult(
        source.id,
        run_id,
        "succeeded",
        jobs_seen=len(raw_jobs),
        jobs_added=jobs_added,
        jobs_updated=jobs_updated,
        jobs_closed=jobs_closed,
    )


def refresh_due_sources(
    conn: StoreConnection,
    adapter_registry: AdapterRegistry,
    source_types: set[str] | None = None,
) -> RefreshSummary:
    params: list[str] = []
    source_type_filter = ""
    if source_types is not None:
        if not source_types:
            rows = []
        else:
            placeholders = ", ".join("?" for _ in source_types)
            source_type_filter = f" AND source_type IN ({placeholders})"
            params = sorted(source_types)
            rows = conn.execute(
                f"""
                SELECT id, source_type FROM job_sources
                WHERE disabled_at IS NULL AND review_status = 'reviewed'
                {source_type_filter}
                ORDER BY id
                """,
                params,
            ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT id, source_type FROM job_sources
            WHERE disabled_at IS NULL AND review_status = 'reviewed'
            ORDER BY id
            """
        ).fetchall()
    sources_attempted = 0
    sources_succeeded = 0
    jobs_seen = 0
    jobs_closed = 0
    failures = 0
    blocked = 0
    suspicious_empty = 0

    for row in rows:
        try:
            adapter = adapter_registry.adapter_for(row["source_type"])
            result = refresh_source(conn, row["id"], adapter)
        except Exception as exc:
            source = _load_source(conn, row["id"])
            run_id = _start_run(conn, source_count=1)
            event_type = (
                exc.event_type
                if isinstance(exc, RefreshError)
                else "manual_review_needed"
            )
            _record_friction(
                conn,
                source=source,
                run_id=run_id,
                event_type=event_type,
                url=source.url,
                details=_failure_details(exc),
                status_code=exc.status_code if isinstance(exc, RefreshError) else None,
            )
            _finish_run(conn, run_id, status="failed", error=str(exc))
            result = RefreshResult(source.id, run_id, "failed")

        sources_attempted += 1
        sources_succeeded += int(result.status == "succeeded")
        jobs_seen += result.jobs_seen
        jobs_closed += result.jobs_closed
        failures += int(result.status == "failed")
        blocked += int(result.status == "blocked")
        suspicious_empty += int(result.status == "suspicious_empty")

    return RefreshSummary(
        sources_seen=len(rows),
        sources_attempted=sources_attempted,
        sources_succeeded=sources_succeeded,
        sources_refreshed=sources_succeeded,
        jobs_seen=jobs_seen,
        jobs_closed=jobs_closed,
        failures=failures,
        blocked=blocked,
        suspicious_empty=suspicious_empty,
    )


def _empty_result_details(source: JobSource) -> dict[str, object]:
    recommendation = (
        "Careers landing page returned zero jobs. The HTTP adapter checks JSON-LD, "
        "embedded ATS URLs, and same-domain job links. Seed extra_sources (Greenhouse, "
        "Lever, Ashby) usually cover JS-heavy pages without browser automation."
        if source.source_type == "careers"
        else "Check whether the public ATS board is empty, stale, or changed its public API shape."
    )
    return {
        "reason": "adapter_returned_zero_jobs",
        "stage": "fetch_jobs",
        "source_type": source.source_type,
        "recommendation": recommendation,
    }


def _failure_details(exc: Exception) -> dict[str, object]:
    details: dict[str, object] = {"error": str(exc)}
    if isinstance(exc, RefreshError):
        details["event_type"] = exc.event_type
        if exc.status_code is not None:
            details["status_code"] = exc.status_code
        if exc.event_type == "rate_limited":
            details["recommendation"] = (
                "Retry later or reduce refresh cadence for this source; keep the "
                "source enabled unless rate limits persist."
            )
    return details


def _load_source(conn: StoreConnection, source_id: int) -> JobSource:
    row = conn.execute(
        """
        SELECT id, company_id, url, source_type, policy_mode, review_status
        FROM job_sources
        WHERE id = ?
        """,
        (source_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"Job source not found: {source_id}")
    return JobSource(
        id=row["id"],
        company_id=row["company_id"],
        url=row["url"],
        source_type=row["source_type"],
        policy_mode=row["policy_mode"],
        review_status=row["review_status"],
    )


def _start_run(conn: StoreConnection, *, source_count: int) -> int:
    cursor = conn.execute(
        "INSERT INTO ingestion_runs (source_count) VALUES (?)",
        (source_count,),
    )
    conn.commit()
    return int(cursor.lastrowid)


def _finish_run(
    conn: StoreConnection,
    run_id: int,
    *,
    status: str,
    jobs_seen: int = 0,
    jobs_added: int = 0,
    jobs_updated: int = 0,
    jobs_closed: int = 0,
    error: str | None = None,
) -> None:
    conn.execute(
        """
        UPDATE ingestion_runs
        SET
          finished_at = CURRENT_TIMESTAMP,
          status = ?,
          jobs_seen = ?,
          jobs_added = ?,
          jobs_updated = ?,
          jobs_closed = ?,
          error = ?
        WHERE id = ?
        """,
        (status, jobs_seen, jobs_added, jobs_updated, jobs_closed, error, run_id),
    )
    conn.commit()


def _record_friction(
    conn: StoreConnection,
    *,
    source: JobSource,
    run_id: int,
    event_type: str,
    url: str,
    details: dict[str, object],
    status_code: int | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO source_friction_events (
          job_source_id,
          ingestion_run_id,
          event_type,
          url,
          status_code,
          details_json
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            source.id,
            run_id,
            event_type,
            url,
            status_code,
            json.dumps(details, sort_keys=True),
        ),
    )
    conn.commit()


def _insert_snapshot(
    conn: StoreConnection,
    run_id: int,
    source: JobSource,
    raw_job: RawJob,
    content_hash: str,
) -> None:
    conn.execute(
        """
        INSERT INTO job_snapshots (
          ingestion_run_id,
          job_source_id,
          external_id,
          title,
          company_name,
          location_text,
          remote_mode,
          raw_json,
          content_hash
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id,
            source.id,
            raw_job.external_id,
            raw_job.title,
            _company_name(conn, source.company_id),
            raw_job.location_text,
            raw_job.remote_mode,
            json.dumps(asdict(raw_job), sort_keys=True),
            content_hash,
        ),
    )


def _insert_job(
    conn: StoreConnection,
    source: JobSource,
    raw_job: RawJob,
    content_hash: str,
) -> int:
    cursor = conn.execute(
        """
        INSERT INTO jobs (
          company_id,
          job_source_id,
          external_id,
          title,
          department,
          location_text,
          remote_mode,
          employment_type,
          seniority,
          description_text,
          requirements_text,
          apply_url,
          source_url,
          content_hash
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        _job_params(source, raw_job, content_hash),
    )
    return int(cursor.lastrowid)


def _update_job(
    conn: StoreConnection,
    job_id: int,
    source: JobSource,
    raw_job: RawJob,
    content_hash: str,
) -> None:
    conn.execute(
        """
        UPDATE jobs
        SET
          job_source_id = ?,
          external_id = ?,
          title = ?,
          department = ?,
          location_text = ?,
          remote_mode = ?,
          employment_type = ?,
          seniority = ?,
          description_text = ?,
          requirements_text = ?,
          apply_url = ?,
          source_url = ?,
          content_hash = ?,
          last_seen_at = CURRENT_TIMESTAMP,
          status = 'open'
        WHERE id = ?
        """,
        (
            source.id,
            raw_job.external_id,
            raw_job.title,
            raw_job.department,
            raw_job.location_text,
            raw_job.remote_mode,
            raw_job.employment_type,
            raw_job.seniority,
            raw_job.description_text,
            raw_job.requirements_text,
            raw_job.apply_url,
            raw_job.source_url or source.url,
            content_hash,
            job_id,
        ),
    )


def _find_existing_job(
    conn: StoreConnection,
    company_id: int,
    raw_job: RawJob,
    content_hash: str,
) -> int | None:
    if raw_job.external_id:
        row = conn.execute(
            "SELECT id FROM jobs WHERE company_id = ? AND external_id = ?",
            (company_id, raw_job.external_id),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT id FROM jobs WHERE company_id = ? AND content_hash = ?",
            (company_id, content_hash),
        ).fetchone()
    return None if row is None else int(row["id"])


def _close_stale_jobs(
    conn: StoreConnection,
    source: JobSource,
    seen_job_ids: set[int],
) -> int:
    if not seen_job_ids:
        return 0
    placeholders = ", ".join("?" for _ in seen_job_ids)
    cursor = conn.execute(
        f"""
        UPDATE jobs
        SET status = 'closed'
        WHERE job_source_id = ?
          AND status = 'open'
          AND id NOT IN ({placeholders})
        """,
        (source.id, *sorted(seen_job_ids)),
    )
    return int(cursor.rowcount or 0)


def _job_params(
    source: JobSource,
    raw_job: RawJob,
    content_hash: str,
) -> tuple[object, ...]:
    return (
        source.company_id,
        source.id,
        raw_job.external_id,
        raw_job.title,
        raw_job.department,
        raw_job.location_text,
        raw_job.remote_mode,
        raw_job.employment_type,
        raw_job.seniority,
        raw_job.description_text,
        raw_job.requirements_text,
        raw_job.apply_url,
        raw_job.source_url or source.url,
        content_hash,
    )


def _mark_source_checked(conn: StoreConnection, source_id: int) -> None:
    conn.execute(
        """
        UPDATE job_sources
        SET last_checked_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (source_id,),
    )
    conn.commit()


def _company_name(conn: StoreConnection, company_id: int) -> str:
    row = conn.execute("SELECT name FROM companies WHERE id = ?", (company_id,)).fetchone()
    if row is None:
        raise ValueError(f"Company not found: {company_id}")
    return str(row["name"])


def _content_hash(raw_job: RawJob) -> str:
    payload = json.dumps(asdict(raw_job), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
