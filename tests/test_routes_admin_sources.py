import csv
import io
import json
from pathlib import Path

from fastapi.testclient import TestClient

from ml_job_swarm.app import create_app, create_app_from_env
from ml_job_swarm.adapters import CareersJsonLdAdapter
from ml_job_swarm.catalog import submit_company_source
from ml_job_swarm.ingest import AdapterRegistry, RawJob


class FakeAdapter:
    def __init__(self, jobs=None):
        self.jobs = jobs or []
        self.calls = 0

    def fetch_jobs(self, source):
        self.calls += 1
        return self.jobs


def test_admin_sources_page_lists_source_health():
    app = create_app()
    source_id = _seed_source(app.state.conn)
    client = TestClient(app)

    response = client.get("/admin/sources")

    assert response.status_code == 200
    assert "Example AI" in response.text
    assert "https://boards.greenhouse.io/example" in response.text
    assert f'data-source-id="{source_id}"' in response.text
    assert "reviewed" in response.text
    assert 'href="/admin/audit"' in response.text
    assert 'href="/admin/runs"' in response.text
    assert 'href="/admin/sources/friction"' in response.text
    assert 'href="/sources/new"' in response.text


def test_admin_sources_page_exposes_refresh_action():
    app = create_app()
    _seed_source(app.state.conn)
    client = TestClient(app)

    response = client.get("/admin/sources")

    assert response.status_code == 200
    assert 'action="/admin/sources/refresh"' in response.text
    assert "Refresh sources" in response.text


def test_admin_sources_page_exposes_single_source_refresh_action():
    app = create_app()
    source_id = _seed_source(app.state.conn)
    client = TestClient(app)

    response = client.get("/admin/sources")

    assert response.status_code == 200
    assert f'action="/admin/sources/{source_id}/refresh"' in response.text
    assert "Refresh" in response.text


def test_admin_sources_page_marks_supported_sources_ready_to_refresh():
    app = create_app()
    source_id = _seed_source(app.state.conn)
    client = TestClient(app)

    response = client.get("/admin/sources")

    source_row = response.text.split(f'data-source-id="{source_id}"', 1)[1].split(
        "</tr>",
        1,
    )[0]
    assert response.status_code == 200
    assert "Support" in response.text
    assert "Adapter ready" in source_row
    assert "Unchecked" in source_row
    assert f'action="/admin/sources/{source_id}/refresh"' in source_row


def test_admin_sources_page_marks_successfully_checked_sources_healthy():
    app = create_app()
    source_id = _seed_source(app.state.conn)
    source = app.state.conn.execute(
        "SELECT company_id FROM job_sources WHERE id = ?",
        (source_id,),
    ).fetchone()
    app.state.conn.execute(
        """
        INSERT INTO jobs (
          company_id,
          job_source_id,
          external_id,
          title,
          source_url,
          content_hash,
          status
        )
        VALUES (?, ?, ?, ?, ?, ?, 'open')
        """,
        (
            source["company_id"],
            source_id,
            "healthy-job",
            "Healthy ML Engineer",
            "https://boards.greenhouse.io/example/jobs/healthy",
            "healthy-hash",
        ),
    )
    app.state.conn.execute(
        "UPDATE job_sources SET last_checked_at = ? WHERE id = ?",
        ("2026-05-11 11:00:00", source_id),
    )
    app.state.conn.commit()
    client = TestClient(app)

    response = client.get("/admin/sources")

    source_row = response.text.split(f'data-source-id="{source_id}"', 1)[1].split(
        "</tr>",
        1,
    )[0]
    assert response.status_code == 200
    assert "Adapter ready" in source_row
    assert "Healthy" in source_row


def test_admin_sources_page_marks_current_friction_as_needs_review():
    app = create_app()
    source_id = _seed_source(app.state.conn)
    _seed_friction(app.state.conn, source_id, "blocked_response")
    client = TestClient(app)

    response = client.get("/admin/sources")

    source_row = response.text.split(f'data-source-id="{source_id}"', 1)[1].split(
        "</tr>",
        1,
    )[0]
    assert response.status_code == 200
    assert "Needs review" in source_row
    assert "blocked_response" in source_row


def test_admin_sources_page_marks_unsupported_sources_without_refresh_action():
    app = create_app()
    source_id = _seed_source(
        app.state.conn,
        company_name="Custom Careers",
        normalized_name="custom careers",
        source_type="custom",
        url="https://example.com/careers",
    )
    client = TestClient(app)

    response = client.get("/admin/sources")

    source_row = response.text.split(f'data-source-id="{source_id}"', 1)[1].split(
        "</tr>",
        1,
    )[0]
    assert response.status_code == 200
    assert "No adapter" in source_row
    assert f'action="/admin/sources/{source_id}/refresh"' not in source_row
    assert f'action="/admin/sources/{source_id}/disable"' in source_row


def test_admin_sources_page_shows_source_support_summary():
    app = create_app()
    _seed_source(app.state.conn)
    _seed_source(
        app.state.conn,
        company_name="Custom Careers",
        normalized_name="custom careers",
        source_type="custom",
        url="https://example.com/careers",
    )
    _seed_source(
        app.state.conn,
        disabled=True,
        company_name="Disabled AI",
        normalized_name="disabled ai",
        source_type="greenhouse",
        url="https://boards.greenhouse.io/disabledai",
    )
    client = TestClient(app)

    response = client.get("/admin/sources")

    assert response.status_code == 200
    assert "Source coverage" in response.text
    assert "Reviewed sources" in response.text
    assert "Refresh-ready" in response.text
    assert "No adapter" in response.text
    assert "Disabled" in response.text
    assert "<dd>3</dd>" in response.text
    assert "<dd>1</dd>" in response.text


def test_runtime_app_factory_imports_seed_catalog_idempotently(monkeypatch, tmp_path):
    seed_path = tmp_path / "seed_companies.json"
    seed_path.write_text(
        json.dumps(
            [
                {
                    "name": "Runtime Seed AI",
                    "aliases": [],
                    "tags": ["ai_infra"],
                    "stage": "growth",
                    "priority_tier": 1,
                    "careers_url": "https://boards.greenhouse.io/runtimeseed",
                    "ats_type": "greenhouse",
                    "reviewed_at": "2026-05-08",
                }
            ]
        )
    )
    db_path = tmp_path / "jobs.db"
    monkeypatch.setenv("ML_JOB_SWARM_DB_PATH", str(db_path))
    monkeypatch.setenv("ML_JOB_SWARM_SEED_COMPANIES", str(seed_path))

    first_app = create_app_from_env()
    second_app = create_app_from_env()
    client = TestClient(second_app)
    response = client.get("/admin/sources")

    company_count = second_app.state.conn.execute(
        "SELECT COUNT(*) FROM companies"
    ).fetchone()[0]
    source_count = second_app.state.conn.execute(
        "SELECT COUNT(*) FROM job_sources"
    ).fetchone()[0]
    assert db_path.exists()
    assert first_app.state.seed_companies_imported == 1
    assert second_app.state.seed_companies_imported == 0
    assert company_count == 1
    assert source_count == 1
    assert response.status_code == 200
    assert "Runtime Seed AI" in response.text
    assert "https://boards.greenhouse.io/runtimeseed" in response.text


def test_admin_pages_render_global_nav_with_active_link():
    app = create_app()
    _seed_source(app.state.conn)
    client = TestClient(app)

    for path in (
        "/admin/sources",
        "/admin/audit",
        "/admin/runs",
        "/admin/sources/friction",
        "/sources/new",
    ):
        response = client.get(path)
        assert response.status_code == 200, path
        assert 'class="global-nav"' in response.text, path
        assert 'href="/onboarding"' in response.text, path
        assert 'href="/dashboard"' in response.text, path
        assert 'href="/admin/sources"' in response.text, path
        assert 'href="/admin/sources" aria-current="page"' in response.text, path


def test_admin_sources_page_shows_last_checked_timestamps():
    app = create_app()
    checked_id = _seed_source(app.state.conn)
    app.state.conn.execute(
        "UPDATE job_sources SET last_checked_at = ? WHERE id = ?",
        ("2026-05-09T12:00:00", checked_id),
    )
    second_company_id = app.state.conn.execute(
        "INSERT INTO companies (name, normalized_name) VALUES (?, ?)",
        ("Sample Labs", "sample labs"),
    ).lastrowid
    never_id = app.state.conn.execute(
        """
        INSERT INTO job_sources (
          company_id, url, source_type, policy_mode, review_status
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            second_company_id,
            "https://jobs.sample-labs.example/careers",
            "greenhouse",
            "allowed",
            "reviewed",
        ),
    ).lastrowid
    app.state.conn.commit()
    client = TestClient(app)

    response = client.get("/admin/sources")

    assert response.status_code == 200
    assert "Last checked" in response.text
    assert "2026-05-09T12:00:00" in response.text
    body_after_never = response.text.split(f'data-source-id="{never_id}"', 1)[1]
    assert "Never" in body_after_never


def test_admin_sources_suppresses_stale_friction_after_successful_recovery():
    app = create_app()
    source_id = _seed_source(app.state.conn)
    _seed_friction(
        app.state.conn,
        source_id,
        "blocked_response",
        details={"recommendation": "manual review"},
    )
    app.state.conn.execute(
        "UPDATE source_friction_events SET created_at = ? WHERE job_source_id = ?",
        ("2026-05-10 10:00:00", source_id),
    )
    source = app.state.conn.execute(
        "SELECT company_id FROM job_sources WHERE id = ?",
        (source_id,),
    ).fetchone()
    app.state.conn.execute(
        """
        INSERT INTO jobs (
          company_id,
          job_source_id,
          external_id,
          title,
          source_url,
          content_hash,
          status
        )
        VALUES (?, ?, ?, ?, ?, ?, 'open')
        """,
        (
            source["company_id"],
            source_id,
            "recovered-job",
            "Recovered ML Engineer",
            "https://boards.greenhouse.io/example/jobs/recovered",
            "recovered-hash",
        ),
    )
    app.state.conn.execute(
        "UPDATE job_sources SET last_checked_at = ? WHERE id = ?",
        ("2026-05-11 10:00:00", source_id),
    )
    app.state.conn.commit()
    client = TestClient(app)

    response = client.get("/admin/sources")
    friction = client.get("/admin/sources/friction")

    source_row = response.text.split(f'data-source-id="{source_id}"', 1)[1].split(
        "</tr>",
        1,
    )[0]
    assert response.status_code == 200
    assert "Friction: none" in source_row
    assert "healthy" in source_row
    assert "blocked_response" not in source_row
    assert friction.status_code == 200
    assert "blocked_response" in friction.text


def test_admin_sources_page_shows_enable_for_disabled_source():
    app = create_app()
    source_id = _seed_source(app.state.conn, disabled=True)
    client = TestClient(app)

    response = client.get("/admin/sources")

    assert response.status_code == 200
    assert f'action="/admin/sources/{source_id}/enable"' in response.text
    assert f'action="/admin/sources/{source_id}/disable"' not in response.text
    assert f'action="/admin/sources/{source_id}/refresh"' not in response.text
    assert "Enable" in response.text
    assert "Disabled" in response.text


def test_new_source_page_renders_submission_form():
    app = create_app()
    client = TestClient(app)

    response = client.get("/sources/new")

    assert response.status_code == 200
    assert "Add company source" in response.text
    assert 'name="company_name"' in response.text
    assert 'name="source_url"' in response.text


def test_new_source_page_preflights_public_ats_source():
    app = create_app()
    client = TestClient(app)

    response = client.get(
        "/sources/new",
        params={
            "company_name": "Example AI",
            "source_url": "https://jobs.ashbyhq.com/example",
        },
    )

    assert response.status_code == 200
    assert "Source preflight" in response.text
    assert "allowed:public_ats" in response.text
    assert "ashby" in response.text
    assert "Ready to refresh after review" in response.text
    assert 'action="/sources/new"' in response.text
    assert 'type="hidden" name="company_name" value="Example AI"' in response.text


def test_new_source_page_preflights_unknown_public_source_as_manual_only():
    app = create_app()
    client = TestClient(app)

    response = client.get(
        "/sources/new",
        params={
            "company_name": "Example Careers",
            "source_url": "https://example.com/about",
        },
    )

    assert response.status_code == 200
    assert "manual_link:unknown_source" in response.text
    assert "careers" in response.text
    assert "Not refreshable yet" in response.text
    assert "Queue for admin review" in response.text


def test_new_source_page_preflights_restricted_source_without_queue_action():
    app = create_app()
    client = TestClient(app)

    response = client.get(
        "/sources/new",
        params={
            "company_name": "Bad Source Inc",
            "source_url": "https://linkedin.com/company/bad-source/jobs",
        },
    )

    assert response.status_code == 200
    assert "blocked:restricted_source" in response.text
    assert "Cannot queue restricted source" in response.text
    assert 'method="post"' not in response.text


def test_new_source_submission_queues_pending_source():
    app = create_app()
    client = TestClient(app)

    response = client.post(
        "/sources/new",
        data={
            "company_name": "New AI Startup",
            "source_url": "https://newaistartup.example/careers",
        },
        follow_redirects=False,
    )

    queue = app.state.conn.execute(
        """
        SELECT company_name, requested_url, status, reason
        FROM company_source_review_queue
        """
    ).fetchone()
    source_count = app.state.conn.execute("SELECT COUNT(*) FROM job_sources").fetchone()[
        0
    ]
    assert response.status_code == 303
    assert response.headers["location"] == "/admin/sources"
    assert dict(queue) == {
        "company_name": "New AI Startup",
        "requested_url": "https://newaistartup.example/careers",
        "status": "pending",
        "reason": "manual_review_required",
    }
    assert source_count == 0


def test_new_source_submission_preserves_blocked_policy_result():
    app = create_app()
    client = TestClient(app)

    response = client.post(
        "/sources/new",
        data={
            "company_name": "Bad Source Inc",
            "source_url": "https://linkedin.com/company/bad-source/jobs",
        },
        follow_redirects=False,
    )

    queue = app.state.conn.execute(
        "SELECT status, reason FROM company_source_review_queue"
    ).fetchone()
    friction = app.state.conn.execute(
        "SELECT event_type, url FROM source_friction_events"
    ).fetchone()
    assert response.status_code == 303
    assert dict(queue) == {"status": "blocked", "reason": "blocked:restricted_source"}
    assert dict(friction) == {
        "event_type": "policy_blocked",
        "url": "https://linkedin.com/company/bad-source/jobs",
    }


def test_new_source_submission_requires_fields():
    app = create_app()
    client = TestClient(app)

    response = client.post(
        "/sources/new",
        data={"company_name": "", "source_url": ""},
    )

    assert response.status_code == 400
    assert "company_name and source_url are required" in response.text


def test_admin_sources_page_lists_review_queue():
    app = create_app()
    queue_id = submit_company_source(
        app.state.conn,
        company_name="New AI Startup",
        source_url="https://newaistartup.example/careers",
    )
    client = TestClient(app)

    response = client.get("/admin/sources")

    assert response.status_code == 200
    assert "Source review queue" in response.text
    assert "New AI Startup" in response.text
    assert "https://newaistartup.example/careers" in response.text
    assert f'data-review-id="{queue_id}"' in response.text
    assert "manual_review_required" in response.text


def test_admin_sources_page_preflights_review_queue_refreshability():
    app = create_app()
    ready_queue_id = submit_company_source(
        app.state.conn,
        company_name="Workable Startup",
        source_url="https://apply.workable.com/example-ai/",
    )
    manual_queue_id = submit_company_source(
        app.state.conn,
        company_name="Unknown Source",
        source_url="https://example.com/about",
    )
    client = TestClient(app)

    response = client.get("/admin/sources")

    ready_row = response.text.split(f'data-review-id="{ready_queue_id}"', 1)[1].split(
        "</tr>",
        1,
    )[0]
    manual_row = response.text.split(f'data-review-id="{manual_queue_id}"', 1)[1].split(
        "</tr>",
        1,
    )[0]
    assert response.status_code == 200
    assert "Policy" in response.text
    assert "Inferred type" in response.text
    assert "Refreshability" in response.text
    assert "allowed:public_ats" in ready_row
    assert "workable" in ready_row
    assert "Ready" in ready_row
    assert "manual_link:unknown_source" in manual_row
    assert "careers" in manual_row
    assert "Not refreshable" in manual_row


def test_admin_sources_page_exposes_approve_and_refresh_for_pending_queue():
    app = create_app()
    queue_id = submit_company_source(
        app.state.conn,
        company_name="New AI Startup",
        source_url="https://boards.greenhouse.io/newaistartup",
    )
    client = TestClient(app)

    response = client.get("/admin/sources")

    assert response.status_code == 200
    assert f'action="/admin/source-review/{queue_id}/approve-refresh"' in response.text
    assert "Approve and refresh" in response.text


def test_admin_can_approve_queued_source_from_admin_page():
    app = create_app()
    queue_id = submit_company_source(
        app.state.conn,
        company_name="New AI Startup",
        source_url="https://newaistartup.example/careers",
    )
    client = TestClient(app)

    response = client.post(
        f"/admin/source-review/{queue_id}/approve",
        follow_redirects=False,
    )

    queue = app.state.conn.execute(
        "SELECT status FROM company_source_review_queue WHERE id = ?",
        (queue_id,),
    ).fetchone()
    source = app.state.conn.execute(
        """
        SELECT companies.name, job_sources.review_status
        FROM job_sources
        JOIN companies ON companies.id = job_sources.company_id
        """
    ).fetchone()
    audit = app.state.conn.execute(
        "SELECT action, target_type, target_id FROM admin_audit_events"
    ).fetchone()
    assert response.status_code == 303
    assert queue["status"] == "approved"
    assert dict(source) == {
        "name": "New AI Startup",
        "review_status": "reviewed",
    }
    assert dict(audit) == {
        "action": "approve",
        "target_type": "company_source_review_queue",
        "target_id": str(queue_id),
    }


def test_admin_can_approve_and_refresh_public_ats_source_from_admin_page():
    app = create_app()
    queue_id = submit_company_source(
        app.state.conn,
        company_name="New AI Startup",
        source_url="https://boards.greenhouse.io/newaistartup",
    )
    adapter = FakeAdapter(
        [
            RawJob(
                external_id="ml-platform",
                title="Machine Learning Platform Engineer",
                source_url="https://boards.greenhouse.io/newaistartup/jobs/1",
            )
        ]
    )
    app.state.adapter_registry = AdapterRegistry({"greenhouse": adapter})
    client = TestClient(app)

    response = client.post(
        f"/admin/source-review/{queue_id}/approve-refresh",
        follow_redirects=False,
    )

    queue = app.state.conn.execute(
        "SELECT status FROM company_source_review_queue WHERE id = ?",
        (queue_id,),
    ).fetchone()
    source = app.state.conn.execute(
        """
        SELECT job_sources.id, job_sources.last_checked_at, companies.name
        FROM job_sources
        JOIN companies ON companies.id = job_sources.company_id
        """
    ).fetchone()
    job = app.state.conn.execute("SELECT title, source_url FROM jobs").fetchone()
    assert response.status_code == 303
    assert response.headers["location"] == (
        "/admin/runs?refresh_status=completed&sources_seen=1"
        "&sources_attempted=1&sources_succeeded=1&sources_refreshed=1"
        "&sources_skipped=0&jobs_seen=1&jobs_closed=0"
        "&suspicious_empty=0&failures=0&blocked=0"
    )
    assert queue["status"] == "approved"
    assert source["name"] == "New AI Startup"
    assert source["last_checked_at"] is not None
    assert dict(job) == {
        "title": "Machine Learning Platform Engineer",
        "source_url": "https://boards.greenhouse.io/newaistartup/jobs/1",
    }
    assert adapter.calls == 1

    summary = client.get(response.headers["location"])

    assert "Refresh summary" in summary.text
    assert "Jobs seen" in summary.text


def test_admin_approve_and_refresh_skips_unsupported_source_type_without_failure():
    app = create_app()
    queue_id = submit_company_source(
        app.state.conn,
        company_name="Custom Careers",
        source_url="https://customcareers.example/careers",
    )
    app.state.adapter_registry = AdapterRegistry({"greenhouse": FakeAdapter()})
    client = TestClient(app)

    response = client.post(
        f"/admin/source-review/{queue_id}/approve-refresh",
        follow_redirects=False,
    )

    queue = app.state.conn.execute(
        "SELECT status FROM company_source_review_queue WHERE id = ?",
        (queue_id,),
    ).fetchone()
    runs = app.state.conn.execute("SELECT COUNT(*) FROM ingestion_runs").fetchone()[0]
    friction_count = app.state.conn.execute(
        "SELECT COUNT(*) FROM source_friction_events"
    ).fetchone()[0]
    assert response.status_code == 303
    assert response.headers["location"] == (
        "/admin/runs?refresh_status=completed&sources_seen=0"
        "&sources_attempted=0&sources_succeeded=0&sources_refreshed=0"
        "&sources_skipped=1&jobs_seen=0&jobs_closed=0"
        "&suspicious_empty=0&failures=0&blocked=0"
    )
    assert queue["status"] == "approved"
    assert runs == 0
    assert friction_count == 0


def test_admin_approve_and_refresh_careers_jsonld_source_inserts_jobs():
    app = create_app()
    queue_id = submit_company_source(
        app.state.conn,
        company_name="Structured Careers",
        source_url="https://structuredcareers.example/careers",
    )
    app.state.adapter_registry = AdapterRegistry(
        {
            "careers": CareersJsonLdAdapter(
                fetch_text=lambda _url: """
                <script type="application/ld+json">
                {
                  "@type": "JobPosting",
                  "title": "AI Platform Engineer",
                  "description": "Operate model serving.",
                  "url": "https://structuredcareers.example/careers/ai-platform"
                }
                </script>
                """
            )
        }
    )
    client = TestClient(app)

    response = client.post(
        f"/admin/source-review/{queue_id}/approve-refresh",
        follow_redirects=False,
    )

    job = app.state.conn.execute("SELECT title, source_url FROM jobs").fetchone()
    source = app.state.conn.execute(
        "SELECT source_type, last_checked_at FROM job_sources"
    ).fetchone()
    assert response.status_code == 303
    assert response.headers["location"] == (
        "/admin/runs?refresh_status=completed&sources_seen=1"
        "&sources_attempted=1&sources_succeeded=1&sources_refreshed=1"
        "&sources_skipped=0&jobs_seen=1&jobs_closed=0"
        "&suspicious_empty=0&failures=0&blocked=0"
    )
    assert dict(job) == {
        "title": "AI Platform Engineer",
        "source_url": "https://structuredcareers.example/careers/ai-platform",
    }
    assert source["source_type"] == "careers"
    assert source["last_checked_at"] is not None


def test_admin_can_reject_queued_source_from_admin_page():
    app = create_app()
    queue_id = submit_company_source(
        app.state.conn,
        company_name="New AI Startup",
        source_url="https://newaistartup.example/careers",
    )
    client = TestClient(app)

    response = client.post(
        f"/admin/source-review/{queue_id}/reject",
        follow_redirects=False,
    )

    queue = app.state.conn.execute(
        "SELECT status FROM company_source_review_queue WHERE id = ?",
        (queue_id,),
    ).fetchone()
    source_count = app.state.conn.execute("SELECT COUNT(*) FROM job_sources").fetchone()[
        0
    ]
    audit = app.state.conn.execute(
        "SELECT action, target_type, target_id FROM admin_audit_events"
    ).fetchone()
    assert response.status_code == 303
    assert queue["status"] == "rejected"
    assert source_count == 0
    assert dict(audit) == {
        "action": "reject",
        "target_type": "company_source_review_queue",
        "target_id": str(queue_id),
    }


def test_admin_cannot_approve_blocked_queued_source():
    app = create_app()
    queue_id = submit_company_source(
        app.state.conn,
        company_name="Bad Source Inc",
        source_url="https://linkedin.com/company/bad-source/jobs",
    )
    client = TestClient(app)

    response = client.post(
        f"/admin/source-review/{queue_id}/approve",
        follow_redirects=False,
    )

    source_count = app.state.conn.execute("SELECT COUNT(*) FROM job_sources").fetchone()[
        0
    ]
    assert response.status_code == 400
    assert "cannot be approved" in response.text
    assert source_count == 0


def test_latest_friction_event_is_visible():
    app = create_app()
    source_id = _seed_source(app.state.conn)
    _seed_friction(app.state.conn, source_id, "captcha_or_login")
    client = TestClient(app)

    response = client.get("/admin/sources")

    assert response.status_code == 200
    assert "captcha_or_login" in response.text
    assert "manual review" in response.text


def test_latest_rate_limit_friction_shows_retry_recommendation():
    app = create_app()
    source_id = _seed_source(app.state.conn)
    _seed_friction(
        app.state.conn,
        source_id,
        "rate_limited",
        status_code=429,
        details={"recommendation": "Retry later or reduce refresh cadence"},
    )
    client = TestClient(app)

    response = client.get("/admin/sources")

    assert response.status_code == 200
    assert "rate_limited" in response.text
    assert "Retry later or reduce refresh cadence" in response.text


def test_disable_source_records_admin_audit_event():
    app = create_app()
    source_id = _seed_source(app.state.conn)
    client = TestClient(app)

    response = client.post(f"/admin/sources/{source_id}/disable", follow_redirects=False)

    source = app.state.conn.execute(
        "SELECT disabled_at FROM job_sources WHERE id = ?",
        (source_id,),
    ).fetchone()
    audit = app.state.conn.execute(
        "SELECT action, target_type, target_id FROM admin_audit_events"
    ).fetchone()
    assert response.status_code == 303
    assert source["disabled_at"] is not None
    assert dict(audit) == {
        "action": "disable",
        "target_type": "job_source",
        "target_id": str(source_id),
    }


def test_enable_source_records_admin_audit_event():
    app = create_app()
    source_id = _seed_source(app.state.conn, disabled=True)
    client = TestClient(app)

    response = client.post(f"/admin/sources/{source_id}/enable", follow_redirects=False)

    source = app.state.conn.execute(
        "SELECT disabled_at FROM job_sources WHERE id = ?",
        (source_id,),
    ).fetchone()
    audit = app.state.conn.execute(
        "SELECT action, target_type, target_id FROM admin_audit_events"
    ).fetchone()
    assert response.status_code == 303
    assert source["disabled_at"] is None
    assert dict(audit) == {
        "action": "enable",
        "target_type": "job_source",
        "target_id": str(source_id),
    }


def test_enable_source_returns_not_found_for_missing_source():
    app = create_app()
    client = TestClient(app)

    response = client.post("/admin/sources/999/enable")

    assert response.status_code == 404
    assert "Source not found" in response.text


def test_admin_refresh_sources_runs_ingestion_pipeline():
    app = create_app()
    _seed_source(app.state.conn)
    adapter = FakeAdapter(
        [
            RawJob(
                external_id="ml-platform",
                title="Machine Learning Platform Engineer",
                department="Engineering",
                location_text="New York, NY",
                remote_mode="remote",
                description_text="Build ML platform systems.",
                requirements_text="Python and PyTorch.",
                apply_url="https://boards.greenhouse.io/example/jobs/1",
                source_url="https://boards.greenhouse.io/example/jobs/1",
            )
        ]
    )
    app.state.adapter_registry = AdapterRegistry({"greenhouse": adapter})
    client = TestClient(app)

    response = client.post("/admin/sources/refresh", follow_redirects=False)

    run = app.state.conn.execute(
        """
        SELECT status, source_count, jobs_seen, jobs_added, jobs_updated
        FROM ingestion_runs
        """
    ).fetchone()
    job = app.state.conn.execute(
        "SELECT title, source_url FROM jobs"
    ).fetchone()
    source = app.state.conn.execute(
        "SELECT last_checked_at FROM job_sources"
    ).fetchone()
    assert response.status_code == 303
    assert response.headers["location"] == (
        "/admin/runs?refresh_status=completed&sources_seen=1"
        "&sources_attempted=1&sources_succeeded=1&sources_refreshed=1"
        "&sources_skipped=0&jobs_seen=1&jobs_closed=0"
        "&suspicious_empty=0&failures=0&blocked=0"
    )
    assert adapter.calls == 1
    assert dict(run) == {
        "status": "succeeded",
        "source_count": 1,
        "jobs_seen": 1,
        "jobs_added": 1,
        "jobs_updated": 0,
    }
    assert dict(job) == {
        "title": "Machine Learning Platform Engineer",
        "source_url": "https://boards.greenhouse.io/example/jobs/1",
    }
    assert source["last_checked_at"] is not None


def test_admin_refresh_sources_reports_closed_jobs():
    app = create_app()
    _seed_source(app.state.conn)
    first_job = RawJob(
        external_id="stays-open",
        title="Stays Open",
        source_url="https://boards.greenhouse.io/example/jobs/1",
    )
    stale_job = RawJob(
        external_id="goes-stale",
        title="Goes Stale",
        source_url="https://boards.greenhouse.io/example/jobs/2",
    )
    adapter = FakeAdapter([first_job, stale_job])
    app.state.adapter_registry = AdapterRegistry({"greenhouse": adapter})
    client = TestClient(app)

    first_response = client.post("/admin/sources/refresh", follow_redirects=False)
    adapter.jobs = [first_job]
    second_response = client.post("/admin/sources/refresh", follow_redirects=False)

    latest_run = app.state.conn.execute(
        """
        SELECT jobs_seen, jobs_added, jobs_updated, jobs_closed
        FROM ingestion_runs
        ORDER BY id DESC
        LIMIT 1
        """
    ).fetchone()
    statuses = app.state.conn.execute(
        "SELECT title, status FROM jobs ORDER BY title"
    ).fetchall()
    assert first_response.status_code == 303
    assert second_response.status_code == 303
    assert "jobs_closed=1" in second_response.headers["location"]
    assert dict(latest_run) == {
        "jobs_seen": 1,
        "jobs_added": 0,
        "jobs_updated": 1,
        "jobs_closed": 1,
    }
    assert [dict(row) for row in statuses] == [
        {"title": "Goes Stale", "status": "closed"},
        {"title": "Stays Open", "status": "open"},
    ]


def test_admin_refresh_sources_uses_default_public_ats_registry(monkeypatch):
    from ml_job_swarm import adapters

    def fetch_json(url):
        assert url == "https://boards-api.greenhouse.io/v1/boards/example/jobs?content=true"
        return {
            "jobs": [
                {
                    "id": 456,
                    "title": "Live ML Engineer",
                    "location": {"name": "Remote US"},
                    "absolute_url": "https://boards.greenhouse.io/example/jobs/456",
                    "content": "<p>Operate production ML systems.</p>",
                }
            ]
        }

    monkeypatch.setattr(adapters, "_default_fetch_json", fetch_json)
    app = create_app()
    _seed_source(app.state.conn)
    client = TestClient(app)

    response = client.post("/admin/sources/refresh", follow_redirects=False)

    job = app.state.conn.execute(
        "SELECT title, location_text, source_url FROM jobs"
    ).fetchone()
    assert response.status_code == 303
    assert dict(job) == {
        "title": "Live ML Engineer",
        "location_text": "Remote US",
        "source_url": "https://boards.greenhouse.io/example/jobs/456",
    }


def test_admin_refresh_sources_filters_to_registry_source_types_and_reports_skips():
    app = create_app()
    _seed_source(app.state.conn)
    _seed_source(
        app.state.conn,
        company_name="Custom Careers",
        normalized_name="custom careers",
        source_type="custom",
        url="https://example.com/careers",
    )
    adapter = FakeAdapter(
        [
            RawJob(
                external_id="ml-platform",
                title="Machine Learning Platform Engineer",
                source_url="https://boards.greenhouse.io/example/jobs/1",
            )
        ]
    )
    app.state.adapter_registry = AdapterRegistry({"greenhouse": adapter})
    client = TestClient(app)

    response = client.post("/admin/sources/refresh", follow_redirects=False)

    runs = app.state.conn.execute(
        "SELECT status, error FROM ingestion_runs ORDER BY id"
    ).fetchall()
    friction_count = app.state.conn.execute(
        "SELECT COUNT(*) FROM source_friction_events"
    ).fetchone()[0]
    assert response.status_code == 303
    assert response.headers["location"] == (
        "/admin/runs?refresh_status=completed&sources_seen=1"
        "&sources_attempted=1&sources_succeeded=1&sources_refreshed=1"
        "&sources_skipped=1&jobs_seen=1&jobs_closed=0"
        "&suspicious_empty=0&failures=0&blocked=0"
    )
    assert adapter.calls == 1
    assert [dict(row) for row in runs] == [{"status": "succeeded", "error": None}]
    assert friction_count == 0

    summary = client.get(response.headers["location"])

    assert summary.status_code == 200
    assert "Refresh summary" in summary.text
    assert "Sources skipped" in summary.text
    assert "Suspicious empty" in summary.text
    assert "1" in summary.text


def test_admin_refresh_single_source_runs_ingestion_pipeline():
    app = create_app()
    source_id = _seed_source(app.state.conn)
    adapter = FakeAdapter(
        [
            RawJob(
                external_id="ml-platform",
                title="Machine Learning Platform Engineer",
                department="Engineering",
                location_text="New York, NY",
                remote_mode="remote",
                description_text="Build ML platform systems.",
                requirements_text="Python and PyTorch.",
                apply_url="https://boards.greenhouse.io/example/jobs/1",
                source_url="https://boards.greenhouse.io/example/jobs/1",
            )
        ]
    )
    app.state.adapter_registry = AdapterRegistry({"greenhouse": adapter})
    client = TestClient(app)

    response = client.post(
        f"/admin/sources/{source_id}/refresh",
        follow_redirects=False,
    )

    run = app.state.conn.execute(
        """
        SELECT status, source_count, jobs_seen, jobs_added, jobs_updated
        FROM ingestion_runs
        """
    ).fetchone()
    job = app.state.conn.execute(
        "SELECT title, source_url FROM jobs"
    ).fetchone()
    source = app.state.conn.execute(
        "SELECT last_checked_at FROM job_sources WHERE id = ?",
        (source_id,),
    ).fetchone()
    assert response.status_code == 303
    assert response.headers["location"] == (
        "/admin/runs?refresh_status=completed&sources_seen=1"
        "&sources_attempted=1&sources_succeeded=1&sources_refreshed=1"
        "&sources_skipped=0&jobs_seen=1&jobs_closed=0"
        "&suspicious_empty=0&failures=0&blocked=0"
    )
    assert adapter.calls == 1
    assert dict(run) == {
        "status": "succeeded",
        "source_count": 1,
        "jobs_seen": 1,
        "jobs_added": 1,
        "jobs_updated": 0,
    }
    assert dict(job) == {
        "title": "Machine Learning Platform Engineer",
        "source_url": "https://boards.greenhouse.io/example/jobs/1",
    }
    assert source["last_checked_at"] is not None


def test_admin_refresh_single_source_skips_unsupported_source_type():
    app = create_app()
    source_id = _seed_source(
        app.state.conn,
        company_name="Custom Careers",
        normalized_name="custom careers",
        source_type="custom",
        url="https://example.com/careers",
    )
    adapter = FakeAdapter([RawJob(external_id="skip", title="Should Not Run")])
    app.state.adapter_registry = AdapterRegistry({"greenhouse": adapter})
    client = TestClient(app)

    response = client.post(
        f"/admin/sources/{source_id}/refresh",
        follow_redirects=False,
    )

    run_count = app.state.conn.execute(
        "SELECT COUNT(*) FROM ingestion_runs"
    ).fetchone()[0]
    friction_count = app.state.conn.execute(
        "SELECT COUNT(*) FROM source_friction_events"
    ).fetchone()[0]
    assert response.status_code == 303
    assert response.headers["location"] == (
        "/admin/runs?refresh_status=completed&sources_seen=0"
        "&sources_attempted=0&sources_succeeded=0&sources_refreshed=0"
        "&sources_skipped=1&jobs_seen=0&jobs_closed=0"
        "&suspicious_empty=0&failures=0&blocked=0"
    )
    assert adapter.calls == 0
    assert run_count == 0
    assert friction_count == 0


def test_admin_refresh_single_source_rejects_disabled_source():
    app = create_app()
    source_id = _seed_source(app.state.conn, disabled=True)
    adapter = FakeAdapter([RawJob(external_id="disabled", title="Should Not Run")])
    app.state.adapter_registry = AdapterRegistry({"greenhouse": adapter})
    client = TestClient(app)

    response = client.post(f"/admin/sources/{source_id}/refresh")

    assert response.status_code == 400
    assert "Source disabled" in response.text
    assert adapter.calls == 0
    assert (
        app.state.conn.execute("SELECT COUNT(*) FROM ingestion_runs").fetchone()[0]
        == 0
    )


def test_admin_refresh_single_source_returns_not_found_for_missing_source():
    app = create_app()
    adapter = FakeAdapter([RawJob(external_id="missing", title="Should Not Run")])
    app.state.adapter_registry = AdapterRegistry({"greenhouse": adapter})
    client = TestClient(app)

    response = client.post("/admin/sources/999/refresh")

    assert response.status_code == 404
    assert "Source not found" in response.text
    assert adapter.calls == 0


def test_admin_refresh_single_source_empty_result_surfaces_diagnostic():
    app = create_app()
    source_id = _seed_source(
        app.state.conn,
        company_name="Custom Careers",
        normalized_name="custom careers",
        source_type="careers",
        url="https://example.com/careers",
    )
    app.state.adapter_registry = AdapterRegistry({"careers": FakeAdapter([])})
    client = TestClient(app)

    response = client.post(
        f"/admin/sources/{source_id}/refresh",
        follow_redirects=False,
    )

    source_health = client.get("/admin/sources")

    assert response.status_code == 303
    assert response.headers["location"] == (
        "/admin/runs?refresh_status=completed&sources_seen=1"
        "&sources_attempted=1&sources_succeeded=0&sources_refreshed=0"
        "&sources_skipped=0&jobs_seen=0&jobs_closed=0"
        "&suspicious_empty=1&failures=0&blocked=0"
    )
    assert "empty_suspicious" in source_health.text
    assert "extra_sources" in source_health.text


def test_export_friction_csv_has_no_secrets_or_raw_resume_text():
    app = create_app()
    source_id = _seed_source(app.state.conn)
    _seed_friction(
        app.state.conn,
        source_id,
        "blocked_response",
        details={
            "safe": "layout changed",
            "cookie": "session=secret",
            "raw_resume_text": "PRIVATE RESUME",
            "token": "secret-token",
            "access_token": "access-secret",
            "api_key": "api-secret",
            "session_cookie": "cookie-secret",
        },
    )
    client = TestClient(app)

    response = client.get("/admin/sources/friction.csv")

    assert response.status_code == 200
    assert "blocked_response" in response.text
    assert "layout changed" in response.text
    assert "session=secret" not in response.text
    assert "PRIVATE RESUME" not in response.text
    assert "secret-token" not in response.text
    assert "access-secret" not in response.text
    assert "api-secret" not in response.text
    assert "cookie-secret" not in response.text


def test_export_friction_csv_includes_sanitized_review_fields():
    app = create_app()
    source_id = _seed_source(app.state.conn)
    _seed_friction(
        app.state.conn,
        source_id,
        "blocked_response",
        review_status="reviewed",
        review_note="safe note token=secret-token",
    )
    client = TestClient(app)

    response = client.get("/admin/sources/friction.csv")

    assert response.status_code == 200
    assert "review_status" in response.text
    assert "review_note" in response.text
    assert "reviewed" in response.text
    assert "[redacted]" in response.text
    assert "secret-token" not in response.text


def test_export_friction_csv_neutralizes_spreadsheet_formulas():
    app = create_app()
    source_id = _seed_source(app.state.conn)
    event_id = _seed_friction(
        app.state.conn,
        source_id,
        "blocked_response",
        review_status="reviewed",
        review_note="=1+1",
    )
    client = TestClient(app)

    response = client.get("/admin/sources/friction.csv")

    stored_note = app.state.conn.execute(
        "SELECT review_note FROM source_friction_events WHERE id = ?",
        (event_id,),
    ).fetchone()["review_note"]
    rows = list(csv.DictReader(io.StringIO(response.text)))
    assert response.status_code == 200
    assert stored_note == "=1+1"
    assert rows[0]["review_note"] == "'=1+1"


def test_source_friction_csv_redacts_sensitive_values_under_safe_keys():
    app = create_app()
    source_id = _seed_source(app.state.conn)
    _seed_friction(
        app.state.conn,
        source_id,
        "blocked_response",
        details={
            "safe": "layout changed",
            "message": "session=secret-cookie",
            "nested": {"note": "raw resume PRIVATE TEXT"},
        },
    )
    client = TestClient(app)

    response = client.get("/admin/sources/friction.csv")

    assert response.status_code == 200
    assert "layout changed" in response.text
    assert "[redacted]" in response.text
    assert "secret-cookie" not in response.text
    assert "PRIVATE TEXT" not in response.text


def test_source_friction_page_handles_empty_state():
    app = create_app()
    client = TestClient(app)

    response = client.get("/admin/sources/friction")

    assert response.status_code == 200
    assert "Source friction" in response.text
    assert "No source friction events" in response.text


def test_source_friction_page_lists_sanitized_events():
    app = create_app()
    source_id = _seed_source(app.state.conn)
    _seed_friction(
        app.state.conn,
        source_id,
        "captcha_or_login",
        status_code=403,
        details={
            "safe": "login required",
            "cookie": "session=secret",
            "raw_resume_text": "PRIVATE RESUME",
            "token": "secret-token",
        },
    )
    client = TestClient(app)

    response = client.get("/admin/sources/friction")

    assert response.status_code == 200
    assert "Source friction" in response.text
    assert "Example AI" in response.text
    assert "https://boards.greenhouse.io/example" in response.text
    assert "captcha_or_login" in response.text
    assert "403" in response.text
    assert "login required" in response.text
    assert "session=secret" not in response.text
    assert "PRIVATE RESUME" not in response.text
    assert "secret-token" not in response.text


def test_source_friction_page_shows_unreviewed_status_and_review_form():
    app = create_app()
    source_id = _seed_source(app.state.conn)
    event_id = _seed_friction(app.state.conn, source_id, "captcha_or_login")
    client = TestClient(app)

    response = client.get("/admin/sources/friction")

    assert response.status_code == 200
    assert "unreviewed" in response.text
    assert f'action="/admin/sources/friction/{event_id}/review"' in response.text
    assert 'name="review_status" value="reviewed"' in response.text
    assert 'name="review_status" value="resolved"' in response.text
    assert 'name="review_note"' in response.text


def test_source_friction_review_updates_status_with_sanitized_note_and_audit():
    app = create_app()
    source_id = _seed_source(app.state.conn)
    event_id = _seed_friction(app.state.conn, source_id, "captcha_or_login")
    client = TestClient(app)

    response = client.post(
        f"/admin/sources/friction/{event_id}/review",
        data={
            "review_status": "reviewed",
            "review_note": "safe note token=secret-token",
        },
        follow_redirects=False,
    )

    event = app.state.conn.execute(
        """
        SELECT review_status, reviewed_at, reviewed_by, review_note
        FROM source_friction_events
        WHERE id = ?
        """,
        (event_id,),
    ).fetchone()
    audit = app.state.conn.execute(
        """
        SELECT action, target_type, target_id, after_json
        FROM admin_audit_events
        """
    ).fetchone()
    assert response.status_code == 303
    assert response.headers["location"] == "/admin/sources/friction"
    assert event["review_status"] == "reviewed"
    assert event["reviewed_at"] is not None
    assert event["reviewed_by"] == "local-admin"
    assert event["review_note"] == "[redacted]"
    assert dict(audit) == {
        "action": "review_friction",
        "target_type": "source_friction_event",
        "target_id": str(event_id),
        "after_json": json.dumps(
            {
                "review_note": "[redacted]",
                "review_status": "reviewed",
            },
            sort_keys=True,
        ),
    }


def test_source_friction_review_rejects_invalid_status():
    app = create_app()
    source_id = _seed_source(app.state.conn)
    event_id = _seed_friction(app.state.conn, source_id, "captcha_or_login")
    client = TestClient(app)

    response = client.post(
        f"/admin/sources/friction/{event_id}/review",
        data={"review_status": "ignored"},
    )

    assert response.status_code == 400
    assert "Invalid review status" in response.text


def test_source_friction_review_returns_not_found_for_missing_event():
    app = create_app()
    client = TestClient(app)

    response = client.post(
        "/admin/sources/friction/999/review",
        data={"review_status": "reviewed"},
    )

    assert response.status_code == 404
    assert "Friction event not found" in response.text


def test_admin_audit_page_handles_empty_state():
    app = create_app()
    client = TestClient(app)

    response = client.get("/admin/audit")

    assert response.status_code == 200
    assert "Admin audit" in response.text
    assert "No admin audit events" in response.text


def test_admin_audit_page_lists_sanitized_events():
    app = create_app()
    app.state.conn.execute(
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
            "local-admin",
            "approve",
            "company_source_review_queue",
            "42",
            json.dumps(
                {
                    "status": "pending",
                    "cookie": "session=secret",
                    "raw_resume_text": "PRIVATE RESUME",
                },
                sort_keys=True,
            ),
            json.dumps(
                {
                    "status": "approved",
                    "token": "secret-token",
                    "safe": "visible",
                },
                sort_keys=True,
            ),
        ),
    )
    app.state.conn.commit()
    client = TestClient(app)

    response = client.get("/admin/audit")

    assert response.status_code == 200
    assert "local-admin" in response.text
    assert "approve" in response.text
    assert "company_source_review_queue" in response.text
    assert "visible" in response.text
    assert "session=secret" not in response.text
    assert "PRIVATE RESUME" not in response.text
    assert "secret-token" not in response.text


def test_admin_audit_page_redacts_sensitive_values_under_safe_keys():
    app = create_app()
    app.state.conn.execute(
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
            "local-admin",
            "review",
            "source_friction_event",
            "7",
            json.dumps(
                {
                    "safe": "visible",
                    "message": "token=secret-token",
                },
                sort_keys=True,
            ),
            json.dumps(
                {
                    "safe_after": "still visible",
                    "nested": {"note": "browser_profile=/tmp/profile"},
                },
                sort_keys=True,
            ),
        ),
    )
    app.state.conn.commit()
    client = TestClient(app)

    response = client.get("/admin/audit")

    assert response.status_code == 200
    assert "visible" in response.text
    assert "still visible" in response.text
    assert "[redacted]" in response.text
    assert "secret-token" not in response.text
    assert "/tmp/profile" not in response.text


def test_admin_runs_page_handles_empty_state():
    app = create_app()
    client = TestClient(app)

    response = client.get("/admin/runs")

    assert response.status_code == 200
    assert "Ingestion run history" in response.text
    assert "No ingestion runs" in response.text


def test_admin_runs_page_lists_counts_and_sanitized_error():
    app = create_app()
    app.state.conn.execute(
        """
        INSERT INTO ingestion_runs (
          status,
          source_count,
          jobs_seen,
          jobs_added,
          jobs_updated,
          jobs_closed,
          error,
          finished_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
        (
            "failed",
            3,
            10,
            4,
            6,
            2,
            "<script>alert(1)</script> token=secret-token",
        ),
    )
    app.state.conn.commit()
    client = TestClient(app)

    response = client.get("/admin/runs")

    assert response.status_code == 200
    assert "failed" in response.text
    assert "10" in response.text
    assert "4" in response.text
    assert "6" in response.text
    assert "2" in response.text
    assert "Closed" in response.text
    assert "[redacted]" in response.text
    assert "<script>" not in response.text
    assert "secret-token" not in response.text


def test_admin_runs_page_links_to_run_detail():
    app = create_app()
    run_id = app.state.conn.execute(
        """
        INSERT INTO ingestion_runs (
          status,
          source_count,
          jobs_seen,
          finished_at
        )
        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        """,
        ("succeeded", 1, 1),
    ).lastrowid
    app.state.conn.commit()
    client = TestClient(app)

    response = client.get("/admin/runs")

    assert response.status_code == 200
    assert f'href="/admin/runs/{run_id}"' in response.text


def test_admin_run_detail_lists_snapshots_and_sanitized_friction():
    app = create_app()
    source_id = _seed_source(app.state.conn)
    run_id = app.state.conn.execute(
        """
        INSERT INTO ingestion_runs (
          status,
          source_count,
          jobs_seen,
          jobs_added,
          finished_at,
          error
        )
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
        """,
        ("suspicious_empty", 1, 1, 1, "token=secret-token"),
    ).lastrowid
    app.state.conn.execute(
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
            source_id,
            "job-1",
            "Machine Learning Engineer",
            "Example AI",
            "New York",
            "remote",
            json.dumps({"safe": "metadata"}, sort_keys=True),
            "hash-1",
        ),
    )
    app.state.conn.execute(
        """
        INSERT INTO source_friction_events (
          job_source_id,
          ingestion_run_id,
          event_type,
          url,
          details_json
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            source_id,
            run_id,
            "empty_suspicious",
            "https://boards.greenhouse.io/example",
            json.dumps(
                {
                    "recommendation": "Add a source-specific adapter",
                    "token": "secret-token",
                },
                sort_keys=True,
            ),
        ),
    )
    app.state.conn.commit()
    client = TestClient(app)

    response = client.get(f"/admin/runs/{run_id}")

    assert response.status_code == 200
    assert f"Run #{run_id}" in response.text
    assert "suspicious_empty" in response.text
    assert "Machine Learning Engineer" in response.text
    assert "Example AI" in response.text
    assert "empty_suspicious" in response.text
    assert "Add a source-specific adapter" in response.text
    assert "[redacted]" in response.text
    assert "secret-token" not in response.text


def test_admin_run_detail_returns_not_found_for_missing_run():
    app = create_app()
    client = TestClient(app)

    response = client.get("/admin/runs/999")

    assert response.status_code == 404
    assert "Run not found" in response.text


def _seed_source(
    conn,
    *,
    disabled=False,
    company_name="Example AI",
    normalized_name="example ai",
    source_type="greenhouse",
    url="https://boards.greenhouse.io/example",
):
    company_id = conn.execute(
        """
        INSERT INTO companies (name, normalized_name)
        VALUES (?, ?)
        """,
        (company_name, normalized_name),
    ).lastrowid
    source_id = conn.execute(
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
            "allowed",
            "reviewed",
            "2026-05-08T00:00:00" if disabled else None,
        ),
    ).lastrowid
    conn.commit()
    return source_id


def _seed_friction(
    conn,
    source_id,
    event_type,
    details=None,
    status_code=None,
    review_status="unreviewed",
    review_note="",
):
    event_id = conn.execute(
        """
        INSERT INTO source_friction_events (
          job_source_id,
          event_type,
          url,
          status_code,
          details_json,
          review_status,
          review_note
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            source_id,
            event_type,
            "https://boards.greenhouse.io/example",
            status_code,
            json.dumps(details or {"recommendation": "manual review"}, sort_keys=True),
            review_status,
            review_note,
        ),
    ).lastrowid
    conn.commit()
    return event_id
