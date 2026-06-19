import json
from pathlib import Path

import pytest

from ml_job_swarm.adapters import CareersJsonLdAdapter
from ml_job_swarm.ingest import (
    AdapterRegistry,
    RawJob,
    RefreshError,
    refresh_due_sources,
    refresh_source,
)
from ml_job_swarm.store import connect, init_db


FIXTURES = Path(__file__).parent / "fixtures"


class FakeAdapter:
    def __init__(self, jobs=None, error=None):
        self.jobs = jobs or []
        self.error = error
        self.calls = 0

    def fetch_jobs(self, source):
        self.calls += 1
        if self.error:
            raise self.error
        return self.jobs


def test_refresh_records_ingestion_run():
    conn = _db_with_source()
    source_id = _source_id(conn)
    adapter = FakeAdapter([_job("ml-engineer", "Machine Learning Engineer")])

    result = refresh_source(conn, source_id, adapter)

    run = conn.execute("SELECT * FROM ingestion_runs").fetchone()
    assert result.status == "succeeded"
    assert run["status"] == "succeeded"
    assert run["finished_at"] is not None
    assert run["source_count"] == 1
    assert run["jobs_seen"] == 1
    assert run["jobs_added"] == 1
    assert run["jobs_updated"] == 0
    assert adapter.calls == 1


def test_refresh_inserts_snapshots_and_canonical_jobs():
    conn = _db_with_source()
    source_id = _source_id(conn)
    jobs = _fixture_jobs("greenhouse_jobs.json")

    result = refresh_source(conn, source_id, FakeAdapter(jobs))

    snapshots = conn.execute("SELECT * FROM job_snapshots").fetchall()
    canonical_jobs = conn.execute(
        "SELECT title, department, source_url FROM jobs ORDER BY title"
    ).fetchall()
    assert result.jobs_seen == 2
    assert len(snapshots) == 2
    assert [row["title"] for row in canonical_jobs] == [
        "AI Platform Engineer",
        "Machine Learning Engineer",
    ]
    assert all(row["source_url"].startswith("https://") for row in canonical_jobs)


def test_refresh_dedupes_by_external_id_or_hash():
    conn = _db_with_source()
    source_id = _source_id(conn)

    refresh_source(conn, source_id, FakeAdapter([_job("same-id", "Old Title")]))
    refresh_source(conn, source_id, FakeAdapter([_job("same-id", "Updated Title")]))

    assert conn.execute("SELECT COUNT(*) FROM job_snapshots").fetchone()[0] == 2
    rows = conn.execute("SELECT title FROM jobs").fetchall()
    assert [row["title"] for row in rows] == ["Updated Title"]

    refresh_source(conn, source_id, FakeAdapter([_job(None, "No External ID")]))
    refresh_source(conn, source_id, FakeAdapter([_job(None, "No External ID")]))

    no_external_rows = conn.execute(
        "SELECT COUNT(*) FROM jobs WHERE external_id IS NULL"
    ).fetchone()[0]
    assert no_external_rows == 1


def test_successful_refresh_closes_jobs_missing_from_latest_source():
    conn = _db_with_source()
    source_id = _source_id(conn)

    refresh_source(
        conn,
        source_id,
        FakeAdapter(
            [
                _job("still-open", "Still Open"),
                _job("now-closed", "Now Closed"),
            ]
        ),
    )
    result = refresh_source(
        conn,
        source_id,
        FakeAdapter([_job("still-open", "Still Open")]),
    )

    rows = conn.execute(
        "SELECT external_id, status FROM jobs ORDER BY external_id"
    ).fetchall()
    run = conn.execute(
        "SELECT jobs_closed FROM ingestion_runs ORDER BY id DESC LIMIT 1"
    ).fetchone()
    assert result.status == "succeeded"
    assert result.jobs_closed == 1
    assert run["jobs_closed"] == 1
    assert [dict(row) for row in rows] == [
        {"external_id": "now-closed", "status": "closed"},
        {"external_id": "still-open", "status": "open"},
    ]


def test_successful_refresh_reopens_reappearing_closed_job():
    conn = _db_with_source()
    source_id = _source_id(conn)

    refresh_source(
        conn,
        source_id,
        FakeAdapter(
            [
                _job("reappearing", "Reappearing"),
                _job("steady", "Steady"),
            ]
        ),
    )
    refresh_source(conn, source_id, FakeAdapter([_job("steady", "Steady")]))
    result = refresh_source(
        conn,
        source_id,
        FakeAdapter(
            [
                _job("reappearing", "Reappearing"),
                _job("steady", "Steady"),
            ]
        ),
    )

    statuses = conn.execute(
        "SELECT external_id, status FROM jobs ORDER BY external_id"
    ).fetchall()
    assert result.jobs_closed == 0
    assert [dict(row) for row in statuses] == [
        {"external_id": "reappearing", "status": "open"},
        {"external_id": "steady", "status": "open"},
    ]


def test_failed_refresh_preserves_existing_jobs():
    conn = _db_with_source()
    source_id = _source_id(conn)

    refresh_source(conn, source_id, FakeAdapter([_job("stable", "Stable Job")]))
    result = refresh_source(
        conn,
        source_id,
        FakeAdapter(error=RefreshError("adapter timeout", "timeout")),
    )

    assert result.status == "failed"
    assert result.jobs_closed == 0
    assert conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 1
    assert conn.execute("SELECT status FROM jobs").fetchone()[0] == "open"
    run = conn.execute(
        "SELECT status, error FROM ingestion_runs ORDER BY id DESC LIMIT 1"
    ).fetchone()
    friction = conn.execute(
        "SELECT event_type, details_json FROM source_friction_events"
    ).fetchone()
    assert run["status"] == "failed"
    assert "adapter timeout" in run["error"]
    assert friction["event_type"] == "timeout"


def test_database_error_during_job_processing_finalizes_run():
    conn = _db_with_source()
    source_id = _source_id(conn)

    result = refresh_source(
        conn,
        source_id,
        FakeAdapter([_job("bad-job", None)]),
    )

    run = conn.execute("SELECT status, finished_at, error FROM ingestion_runs").fetchone()
    friction = conn.execute(
        "SELECT event_type, details_json FROM source_friction_events"
    ).fetchone()
    assert result.status == "failed"
    assert run["status"] == "failed"
    assert run["finished_at"] is not None
    assert "NOT NULL" in run["error"]
    assert friction["event_type"] == "manual_review_needed"
    assert "NOT NULL" in friction["details_json"]


def test_refresh_due_sources_continues_after_unexpected_source_failure():
    conn = _db_with_source(source_type="greenhouse")
    _insert_source(conn, source_type="lever", url="https://jobs.lever.co/example")
    registry = AdapterRegistry(
        {
            "greenhouse": FakeAdapter([_job("bad-job", None)]),
            "lever": FakeAdapter(_fixture_jobs("lever_jobs.json")),
        }
    )

    summary = refresh_due_sources(conn, registry)

    assert summary.sources_seen == 2
    assert summary.sources_attempted == 2
    assert summary.sources_succeeded == 1
    assert summary.sources_refreshed == 1
    assert summary.failures == 1
    assert summary.jobs_seen == 1
    assert conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 1
    runs = conn.execute("SELECT status FROM ingestion_runs ORDER BY id").fetchall()
    assert [run["status"] for run in runs] == ["failed", "succeeded"]


def test_refresh_due_sources_counts_suspicious_empty_sources():
    conn = _db_with_source()
    registry = AdapterRegistry({"greenhouse": FakeAdapter([])})

    summary = refresh_due_sources(conn, registry)

    assert summary.sources_seen == 1
    assert summary.sources_attempted == 1
    assert summary.sources_succeeded == 0
    assert summary.sources_refreshed == 0
    assert summary.failures == 0
    assert summary.suspicious_empty == 1
    run = conn.execute("SELECT status FROM ingestion_runs").fetchone()
    friction = conn.execute("SELECT event_type FROM source_friction_events").fetchone()
    assert run["status"] == "suspicious_empty"
    assert friction["event_type"] == "empty_suspicious"


@pytest.mark.parametrize(
    "event_type",
    ["rate_limited", "captcha_or_login", "blocked_response"],
)
def test_adapter_failure_records_specific_friction_event(event_type):
    conn = _db_with_source()
    source_id = _source_id(conn)

    result = refresh_source(
        conn,
        source_id,
        FakeAdapter(error=RefreshError(f"{event_type} failure", event_type)),
    )

    friction = conn.execute(
        "SELECT event_type, details_json FROM source_friction_events"
    ).fetchone()
    assert result.status == "failed"
    assert friction["event_type"] == event_type
    assert event_type in friction["details_json"]


def test_adapter_failure_records_http_status_code_when_available():
    conn = _db_with_source()
    source_id = _source_id(conn)

    result = refresh_source(
        conn,
        source_id,
        FakeAdapter(
            error=RefreshError("blocked by source", "blocked_response", status_code=403)
        ),
    )

    friction = conn.execute(
        "SELECT event_type, status_code, details_json FROM source_friction_events"
    ).fetchone()
    assert result.status == "failed"
    assert friction["event_type"] == "blocked_response"
    assert friction["status_code"] == 403
    assert "blocked by source" in friction["details_json"]


def test_rate_limited_failure_records_retry_recommendation():
    conn = _db_with_source()
    source_id = _source_id(conn)

    result = refresh_source(
        conn,
        source_id,
        FakeAdapter(
            error=RefreshError(
                "too many requests",
                "rate_limited",
                status_code=429,
            )
        ),
    )

    friction = conn.execute(
        "SELECT event_type, status_code, details_json FROM source_friction_events"
    ).fetchone()
    details = json.loads(friction["details_json"])
    assert result.status == "failed"
    assert friction["event_type"] == "rate_limited"
    assert friction["status_code"] == 429
    assert "Retry later" in details["recommendation"]


def test_policy_block_records_friction_event():
    conn = _db_with_source(
        source_url="https://linkedin.com/company/example/jobs",
        policy_mode="blocked",
    )
    source_id = _source_id(conn)
    adapter = FakeAdapter([_job("should-not-fetch", "Should Not Fetch")])

    result = refresh_source(conn, source_id, adapter)

    friction = conn.execute(
        "SELECT event_type, url FROM source_friction_events"
    ).fetchone()
    assert result.status == "blocked"
    assert adapter.calls == 0
    assert dict(friction) == {
        "event_type": "policy_blocked",
        "url": "https://linkedin.com/company/example/jobs",
    }
    assert conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 0


def test_empty_suspicious_does_not_close_all_jobs_immediately():
    conn = _db_with_source()
    source_id = _source_id(conn)

    refresh_source(conn, source_id, FakeAdapter([_job("open-job", "Open Job")]))
    result = refresh_source(conn, source_id, FakeAdapter([]))

    job = conn.execute("SELECT status FROM jobs").fetchone()
    friction = conn.execute(
        "SELECT event_type FROM source_friction_events ORDER BY id DESC LIMIT 1"
    ).fetchone()
    assert result.status == "suspicious_empty"
    assert result.jobs_closed == 0
    assert job["status"] == "open"
    assert friction["event_type"] == "empty_suspicious"


def test_empty_suspicious_records_actionable_diagnostic_details():
    conn = _db_with_source(source_type="careers", source_url="https://example.com/careers")
    source_id = _source_id(conn)

    result = refresh_source(conn, source_id, FakeAdapter([]))

    friction = conn.execute(
        "SELECT event_type, details_json FROM source_friction_events"
    ).fetchone()
    details = json.loads(friction["details_json"])
    assert result.status == "suspicious_empty"
    assert friction["event_type"] == "empty_suspicious"
    assert details["reason"] == "adapter_returned_zero_jobs"
    assert details["stage"] == "fetch_jobs"
    assert details["source_type"] == "careers"
    assert "JSON-LD" in details["recommendation"]
    assert "extra_sources" in details["recommendation"]


def test_refresh_due_sources_uses_registry_by_source_type():
    conn = _db_with_source(source_type="greenhouse")
    _insert_source(conn, source_type="lever", url="https://jobs.lever.co/example")
    registry = AdapterRegistry(
        {
            "greenhouse": FakeAdapter(_fixture_jobs("greenhouse_jobs.json")),
            "lever": FakeAdapter(_fixture_jobs("lever_jobs.json")),
        }
    )

    summary = refresh_due_sources(conn, registry)

    assert summary.sources_seen == 2
    assert summary.sources_attempted == 2
    assert summary.sources_succeeded == 2
    assert summary.sources_refreshed == 2
    assert summary.jobs_seen == 3
    assert summary.jobs_closed == 0
    assert conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 3


def test_refresh_careers_source_delegates_provider_links_into_jobs():
    conn = _db_with_source(
        source_url="https://example.com/careers",
        source_type="careers",
    )
    source_id = _source_id(conn)
    provider = FakeAdapter([_job("linked-job", "Linked Provider Job")])
    adapter = CareersJsonLdAdapter(
        fetch_text=lambda _url: """
        <html>
          <body>
            <a href="https://boards.greenhouse.io/example">See open roles</a>
          </body>
        </html>
        """,
        provider_adapters={"greenhouse": provider},
    )

    result = refresh_source(conn, source_id, adapter)

    rows = conn.execute("SELECT title, source_url FROM jobs").fetchall()
    friction_count = conn.execute(
        "SELECT COUNT(*) FROM source_friction_events"
    ).fetchone()[0]
    assert result.status == "succeeded"
    assert provider.calls == 1
    assert [row["title"] for row in rows] == ["Linked Provider Job"]
    assert rows[0]["source_url"] == "https://boards.greenhouse.io/example/jobs/test"
    assert friction_count == 0


def test_refresh_due_sources_skips_pending_and_disabled_sources():
    conn = _db_with_source(source_type="greenhouse")
    _insert_source(
        conn,
        source_type="greenhouse",
        url="https://boards.greenhouse.io/pending",
        review_status="pending",
    )
    _insert_source(
        conn,
        source_type="greenhouse",
        url="https://boards.greenhouse.io/disabled",
        disabled=True,
    )
    adapter = FakeAdapter([_job("only-reviewed", "Only Reviewed")])
    registry = AdapterRegistry({"greenhouse": adapter})

    summary = refresh_due_sources(conn, registry)

    assert summary.sources_seen == 1
    assert summary.sources_attempted == 1
    assert summary.sources_succeeded == 1
    assert summary.sources_refreshed == 1
    assert adapter.calls == 1
    assert conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 1


def _db_with_source(
    *,
    source_url="https://boards.greenhouse.io/example",
    source_type="greenhouse",
    policy_mode="allowed",
):
    conn = connect()
    init_db(conn)
    conn.execute(
        """
        INSERT INTO companies (name, normalized_name, careers_url, ats_type)
        VALUES ('Example AI', 'example ai', ?, ?)
        """,
        (source_url, source_type),
    )
    _insert_source(conn, source_type=source_type, url=source_url, policy_mode=policy_mode)
    conn.commit()
    return conn


def _insert_source(
    conn,
    *,
    source_type,
    url,
    policy_mode="allowed",
    review_status="reviewed",
    disabled=False,
):
    company_id = conn.execute(
        "SELECT id FROM companies WHERE normalized_name = 'example ai'"
    ).fetchone()["id"]
    conn.execute(
        """
        INSERT INTO job_sources (
          company_id,
          url,
          source_type,
          policy_mode,
          review_status,
          disabled_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            company_id,
            url,
            source_type,
            policy_mode,
            review_status,
            "2026-05-08T00:00:00" if disabled else None,
        ),
    )


def _source_id(conn):
    return conn.execute("SELECT id FROM job_sources ORDER BY id LIMIT 1").fetchone()[0]


def _fixture_jobs(filename):
    return [RawJob(**item) for item in json.loads((FIXTURES / filename).read_text())]


def _job(external_id, title):
    return RawJob(
        external_id=external_id,
        title=title,
        department="Engineering",
        location_text="New York, NY",
        remote_mode="hybrid",
        employment_type="full_time",
        seniority="mid",
        description_text=f"{title} description",
        requirements_text="Python, SQLite",
        apply_url="https://boards.greenhouse.io/example/jobs/test",
        source_url="https://boards.greenhouse.io/example/jobs/test",
    )
