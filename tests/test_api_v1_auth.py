from fastapi.testclient import TestClient

from ml_job_swarm.app import create_app
from ml_job_swarm.profile import create_target_profile
from tests.conftest import admin_auth_env, auth_env, auth_headers, make_token

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


def _seed_owned_profile(app, *, user_id: str) -> int:
    conn = app.state.conn
    conn.execute(
        """
        INSERT INTO resume_assets (
          user_id,
          original_filename,
          content_type,
          storage_path,
          sha256
        )
        VALUES (?, 'resume.pdf', 'application/pdf', '/tmp/resume.pdf', ?)
        """,
        (user_id, f"digest-{user_id}"),
    )
    conn.commit()
    asset_id = conn.execute("SELECT id FROM resume_assets LIMIT 1").fetchone()["id"]
    return create_target_profile(
        conn,
        resume_asset_id=asset_id,
        keywords=KEYWORDS,
        preferences=PREFERENCES,
        user_id=user_id,
    )


def test_api_v1_requires_auth_when_supabase_enabled(tmp_path, auth_env):
    client = TestClient(create_app(tmp_path / "api-auth.db"))

    blocked = client.get("/api/v1/profiles")
    assert blocked.status_code == 401


def test_api_v1_dashboard_denies_other_user_profile(tmp_path, auth_env):
    app = create_app(tmp_path / "api-idor.db")
    profile_id = _seed_owned_profile(app, user_id="owner-a")
    client = TestClient(app)

    denied = client.get(
        f"/api/v1/dashboard?target_profile_id={profile_id}",
        headers=auth_headers("owner-b"),
    )
    assert denied.status_code == 403


def test_api_v1_saved_jobs_denies_other_user_profile(tmp_path, auth_env):
    app = create_app(tmp_path / "api-saved.db")
    profile_id = _seed_owned_profile(app, user_id="owner-a")
    client = TestClient(app)

    denied = client.get(
        f"/api/v1/saved-jobs?target_profile_id={profile_id}",
        headers=auth_headers("owner-b"),
    )
    assert denied.status_code == 403


def test_api_v1_job_decision_denies_other_user_profile(tmp_path, auth_env):
    app = create_app(tmp_path / "api-decision.db")
    profile_id = _seed_owned_profile(app, user_id="owner-a")
    conn = app.state.conn
    company_id = conn.execute(
        "INSERT INTO companies (name, normalized_name, stage) VALUES ('Acme', 'acme', 'growth')"
    ).lastrowid
    job_id = conn.execute(
        """
        INSERT INTO jobs (company_id, external_id, title, source_url, content_hash, status)
        VALUES (?, '1', 'Engineer', 'https://example.com/jobs/1', 'hash-1', 'open')
        """,
        (company_id,),
    ).lastrowid
    conn.commit()
    client = TestClient(app)

    denied = client.post(
        f"/api/v1/jobs/{job_id}/decision",
        headers=auth_headers("owner-b"),
        json={
            "target_profile_id": profile_id,
            "decision": "saved",
            "notes": "",
        },
    )
    assert denied.status_code == 403


def test_api_v1_owner_can_access_dashboard(tmp_path, auth_env):
    app = create_app(tmp_path / "api-owner.db")
    profile_id = _seed_owned_profile(app, user_id="owner-a")
    client = TestClient(app)

    allowed = client.get(
        f"/api/v1/dashboard?target_profile_id={profile_id}",
        headers=auth_headers("owner-a"),
    )
    assert allowed.status_code == 200
    assert allowed.json()["target_profile_id"] == profile_id


def test_api_v1_admin_requires_allowlisted_user(tmp_path, admin_auth_env):
    client = TestClient(create_app(tmp_path / "api-admin.db"))

    denied = client.get(
        "/api/v1/admin/sources",
        headers=auth_headers("regular-user"),
    )
    assert denied.status_code == 403

    allowed = client.get(
        "/api/v1/admin/sources",
        headers=auth_headers("admin-user"),
    )
    assert allowed.status_code == 200


def test_login_next_path_rejects_open_redirect(tmp_path, auth_env):
    client = TestClient(create_app(tmp_path / "login-next.db"))

    response = client.get("/auth/login?next=https://evil.example/phish")
    assert response.status_code == 200
    assert 'nextPath: "/dashboard"' in response.text


def test_api_v1_csv_export_is_formula_safe(tmp_path):
    app = create_app(tmp_path / "csv-safe.db")
    profile_id = _seed_owned_profile(app, user_id="")
    conn = app.state.conn
    company_id = conn.execute(
        "INSERT INTO companies (name, normalized_name, stage) VALUES ('Acme', 'acme', 'growth')"
    ).lastrowid
    job_id = conn.execute(
        """
        INSERT INTO jobs (company_id, external_id, title, source_url, content_hash, status)
        VALUES (?, '1', '=HYPERLINK(\"http://evil\")', 'https://example.com/jobs/1', 'hash-1', 'open')
        """,
        (company_id,),
    ).lastrowid
    conn.execute(
        """
        INSERT INTO job_decisions (job_id, target_profile_id, decision, notes)
        VALUES (?, ?, 'saved', '')
        """,
        (job_id, profile_id),
    )
    conn.commit()
    client = TestClient(app)

    response = client.get(f"/api/v1/saved-jobs/export.csv?target_profile_id={profile_id}")
    assert response.status_code == 200
    assert "'=HYPERLINK" in response.text.splitlines()[1]
