import pytest
from fastapi.testclient import TestClient

from ml_job_swarm.app import create_app
from ml_job_swarm.profile import create_target_profile


PREFERENCES = {
    "role": {"answer": "Machine Learning Engineer"},
    "level": {"answer": "senior"},
    "location": {"answer": "New York"},
    "work_mode": {"answer": "remote"},
    "company_stage": {"answer": "growth"},
}

KEYWORDS = {
    "desired_titles": ["Machine Learning Engineer"],
    "levels": ["senior"],
    "locations": ["New York"],
    "remote_modes": ["remote"],
    "company_stages": ["growth"],
}


def test_app_shell_wraps_primary_pages_without_breaking_nav():
    app = create_app()
    _seed_source(app.state.conn)
    client = TestClient(app)

    for path, active_href in (
        ("/onboarding", "/onboarding"),
        ("/dashboard", "/dashboard"),
        ("/admin/sources", "/admin/sources"),
    ):
        response = client.get(path)

        assert response.status_code == 200
        assert 'class="app-shell"' in response.text
        assert 'class="app-sidebar"' in response.text
        assert 'class="app-content"' in response.text
        assert 'class="local-status"' in response.text
        assert 'class="global-nav"' in response.text
        assert '<main class="page">' in response.text
        assert f'href="{active_href}" aria-current="page"' in response.text


def test_app_shell_reports_local_deployment_status_by_default(monkeypatch):
    _clear_deployment_env(monkeypatch)
    client = TestClient(create_app())

    response = client.get("/dashboard")

    assert response.status_code == 200
    assert "Deployment: Local development" in response.text
    assert "No public URL configured" in response.text


def test_app_shell_reports_configured_public_deployment(monkeypatch):
    _clear_deployment_env(monkeypatch)
    monkeypatch.setenv("ML_JOB_SWARM_PUBLIC_URL", "https://jobs.example.test")
    client = TestClient(create_app())

    response = client.get("/onboarding")

    assert response.status_code == 200
    assert "Deployment: Public URL configured" in response.text
    assert 'href="https://jobs.example.test"' in response.text
    assert "jobs.example.test" in response.text


@pytest.mark.parametrize(
    ("env_key", "env_value", "expected_href", "expected_text"),
    (
        (
            "PUBLIC_URL",
            "jobs-public.example.test",
            "https://jobs-public.example.test",
            "jobs-public.example.test",
        ),
        (
            "RENDER_EXTERNAL_URL",
            "https://ml-job-swarm.onrender.com/",
            "https://ml-job-swarm.onrender.com",
            "ml-job-swarm.onrender.com",
        ),
        (
            "VERCEL_URL",
            "ml-job-swarm.vercel.app",
            "https://ml-job-swarm.vercel.app",
            "ml-job-swarm.vercel.app",
        ),
        (
            "RAILWAY_PUBLIC_DOMAIN",
            "ml-job-swarm.up.railway.app",
            "https://ml-job-swarm.up.railway.app",
            "ml-job-swarm.up.railway.app",
        ),
        (
            "FLY_APP_NAME",
            "ml-job-swarm",
            "https://ml-job-swarm.fly.dev",
            "ml-job-swarm.fly.dev",
        ),
    ),
)
def test_app_shell_reports_fallback_and_provider_public_deployment(
    monkeypatch,
    env_key,
    env_value,
    expected_href,
    expected_text,
):
    _clear_deployment_env(monkeypatch)
    monkeypatch.setenv(env_key, env_value)
    client = TestClient(create_app())

    response = client.get("/dashboard")

    assert response.status_code == 200
    assert "Deployment: Public URL configured" in response.text
    assert f'href="{expected_href}"' in response.text
    assert expected_text in response.text


def test_dashboard_first_run_empty_state_guides_next_actions():
    client = TestClient(create_app())

    response = client.get("/dashboard")

    assert response.status_code == 200
    assert 'class="first-run-empty-state"' in response.text
    assert "Start with your resume and target role" in response.text
    assert "Check source health" in response.text
    assert 'href="/onboarding"' in response.text
    assert 'href="/admin/sources"' in response.text


def test_dashboard_renders_operational_layout_regions():
    app = create_app()
    target_profile_id = _seed_reviewed_job(app.state.conn)
    client = TestClient(app)

    response = client.get(f"/dashboard?target_profile_id={target_profile_id}")

    assert response.status_code == 200
    assert 'class="page-header"' in response.text
    assert 'class="dashboard-shell"' in response.text
    assert 'class="dashboard-actions"' in response.text
    assert 'class="dashboard-primary"' in response.text
    assert 'class="dashboard-sidebar"' in response.text
    assert 'class="fit-review-action"' in response.text
    assert 'class="decision-filters"' in response.text
    assert 'class="company-group"' in response.text
    assert "Senior Machine Learning Engineer" in response.text


def test_dashboard_renders_operator_console_summary():
    app = create_app()
    target_profile_id = _seed_reviewed_job(app.state.conn)
    client = TestClient(app)

    response = client.get(f"/dashboard?target_profile_id={target_profile_id}")

    assert response.status_code == 200
    assert 'class="dashboard-command-center"' in response.text
    assert 'class="dashboard-stat-grid"' in response.text
    assert "Operator queue" in response.text
    assert "Visible matches" in response.text
    assert "Companies" in response.text
    assert "Waiting review" in response.text
    assert "Fit review" in response.text
    assert "Fit review paused" in response.text


def test_app_shell_dashboard_nav_preserves_target_profile_context():
    app = create_app()
    target_profile_id = _seed_reviewed_job(app.state.conn)
    client = TestClient(app)

    response = client.get(f"/jobs/1?target_profile_id={target_profile_id}")

    assert response.status_code == 200
    assert (
        f'href="/dashboard?target_profile_id={target_profile_id}" aria-current="page"'
        in response.text
    )


def test_dashboard_actions_render_as_command_cards():
    app = create_app()
    target_profile_id = _seed_reviewed_job(app.state.conn)
    client = TestClient(app)

    response = client.get(f"/dashboard?target_profile_id={target_profile_id}")

    assert response.status_code == 200
    assert 'class="command-card command-card-refresh"' in response.text
    assert 'class="command-card command-card-match"' in response.text
    assert 'class="command-card command-card-review"' in response.text
    assert "Refresh catalog" in response.text
    assert "Rules + fit review" in response.text
    assert "Fit review only" in response.text


def test_saved_jobs_page_uses_operator_surface():
    app = create_app()
    target_profile_id = _seed_reviewed_job(app.state.conn)
    client = TestClient(app)

    response = client.get(f"/dashboard/saved?target_profile_id={target_profile_id}")

    assert response.status_code == 200
    assert 'class="page-header"' in response.text
    assert 'class="saved-jobs-toolbar"' in response.text
    assert 'class="saved-jobs-panel"' in response.text
    assert 'class="saved-jobs-empty"' in response.text
    assert "No saved jobs" in response.text


def test_job_detail_page_uses_operator_layout():
    app = create_app()
    target_profile_id = _seed_reviewed_job(app.state.conn)
    job_id = app.state.conn.execute(
        "SELECT id FROM jobs WHERE external_id = ?", ("app-shell-job",)
    ).fetchone()["id"]
    client = TestClient(app)

    response = client.get(f"/jobs/{job_id}?target_profile_id={target_profile_id}")

    assert response.status_code == 200
    assert 'class="job-detail-shell"' in response.text
    assert 'class="job-hero"' in response.text
    assert 'class="job-detail-grid"' in response.text
    assert 'class="decision-card"' in response.text
    assert 'class="application-workspace-card"' in response.text
    assert 'class="local-referrals-card"' in response.text
    assert "Application workspace" in response.text


def test_static_css_contains_product_shell_rules():
    client = TestClient(create_app())

    response = client.get("/static/app.css")

    assert response.status_code == 200
    for selector in (
        ".app-shell",
        ".app-sidebar",
        ".dashboard-shell",
        ".dashboard-primary",
        ".dashboard-sidebar",
        ".dashboard-command-center",
        ".command-card",
        ".saved-jobs-toolbar",
        ".job-detail-shell",
        ".local-status",
        "@media",
    ):
        assert selector in response.text


def test_static_css_contains_dashboard_table_overflow_rules():
    client = TestClient(create_app())

    response = client.get("/static/app.css")

    assert response.status_code == 200
    assert ".rules-preview-panel" in response.text
    assert ".unreviewed-jobs-panel" in response.text
    assert "overflow-x: auto" in response.text


def test_admin_sources_uses_operational_source_layout():
    app = create_app()
    _seed_source(app.state.conn)
    client = TestClient(app)

    response = client.get("/admin/sources")

    assert response.status_code == 200
    assert 'class="page-header"' in response.text
    assert 'class="admin-actions"' in response.text
    assert 'class="admin-refresh-action"' in response.text
    assert 'class="source-table-section"' in response.text
    assert "Source review queue" in response.text
    assert "Existing sources" in response.text


def test_admin_sources_renders_metric_cards_and_status_badges():
    app = create_app()
    _seed_source(app.state.conn)
    client = TestClient(app)

    response = client.get("/admin/sources")

    assert response.status_code == 200
    assert 'class="metric-grid source-metrics"' in response.text
    assert 'class="metric-card"' in response.text
    assert 'class="status-badge status-badge-ready"' in response.text
    assert 'class="status-badge status-badge-healthy"' in response.text


def _seed_source(conn):
    company_id = conn.execute(
        "INSERT INTO companies (name, normalized_name) VALUES (?, ?)",
        ("Example AI", "example ai"),
    ).lastrowid
    conn.execute(
        """
        INSERT INTO job_sources (
          company_id, url, source_type, policy_mode, review_status
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            company_id,
            "https://boards.greenhouse.io/example",
            "greenhouse",
            "allowed",
            "reviewed",
        ),
    )
    conn.commit()


def _clear_deployment_env(monkeypatch):
    for key in (
        "ML_JOB_SWARM_PUBLIC_URL",
        "PUBLIC_URL",
        "RENDER_EXTERNAL_URL",
        "RAILWAY_PUBLIC_DOMAIN",
        "FLY_APP_NAME",
        "VERCEL_URL",
    ):
        monkeypatch.delenv(key, raising=False)


def _seed_reviewed_job(conn):
    resume_asset_id = conn.execute(
        """
        INSERT INTO resume_assets (original_filename, content_type, storage_path, sha256)
        VALUES (?, ?, ?, ?)
        """,
        ("resume.pdf", "application/pdf", "/tmp/resume.pdf", "app-shell-sha"),
    ).lastrowid
    target_profile_id = create_target_profile(
        conn,
        resume_asset_id=resume_asset_id,
        keywords=KEYWORDS,
        preferences=PREFERENCES,
    )
    company_id = conn.execute(
        "INSERT INTO companies (name, normalized_name) VALUES (?, ?)",
        ("Example AI", "example ai"),
    ).lastrowid
    job_id = conn.execute(
        """
        INSERT INTO jobs (
          company_id,
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
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            company_id,
            "app-shell-job",
            "Senior Machine Learning Engineer",
            "Engineering",
            "Remote - New York, NY",
            "remote",
            "Full-time",
            "senior",
            "Build ML ranking systems.",
            "Python and PyTorch required.",
            "https://boards.greenhouse.io/example/jobs/1",
            "https://boards.greenhouse.io/example/jobs/1",
            "app-shell-hash",
        ),
    ).lastrowid
    conn.execute(
        """
        INSERT INTO fit_reviews (
          job_id,
          target_profile_id,
          fit_score,
          label,
          reasons_json,
          risks_json,
          recommendation,
          profile_version
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            job_id,
            target_profile_id,
            92,
            "Strong fit",
            '["matches role"]',
            "[]",
            "Review",
            1,
        ),
    )
    conn.commit()
    return target_profile_id
