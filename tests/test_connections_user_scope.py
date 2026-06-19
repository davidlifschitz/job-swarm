import time
from pathlib import Path

import jwt
from fastapi.testclient import TestClient

from ml_job_swarm.app import create_app
from ml_job_swarm.profile import create_target_profile

FIXTURE_CSV = Path(__file__).parent / "fixtures" / "linkedin_connections.csv"
JWT_SECRET = "test-jwt-secret-for-hosted-auth-32b"

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


def _make_token(subject: str) -> str:
    return jwt.encode(
        {
            "sub": subject,
            "aud": "authenticated",
            "exp": int(time.time()) + 3600,
        },
        JWT_SECRET,
        algorithm="HS256",
    )


def _auth_env(monkeypatch) -> None:
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-test-key")
    monkeypatch.setenv("SUPABASE_JWT_SECRET", JWT_SECRET)


def _seed_profile(conn, *, user_id: str | None = None, sha256: str = "scope-route-sha") -> int:
    resume_asset_id = conn.execute(
        """
        INSERT INTO resume_assets (
          user_id,
          original_filename,
          content_type,
          storage_path,
          sha256
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (user_id or "", "resume.pdf", "application/pdf", "/tmp/resume.pdf", sha256),
    ).lastrowid
    return create_target_profile(
        conn,
        resume_asset_id=resume_asset_id,
        keywords=KEYWORDS,
        preferences=PREFERENCES,
        user_id=user_id,
    )


def test_authenticated_users_only_see_their_connections(tmp_path, monkeypatch):
    _auth_env(monkeypatch)
    app = create_app(tmp_path / "connections-scope.db")
    conn = app.state.conn
    profile_a = _seed_profile(conn, user_id="user-a", sha256="scope-route-sha-a")
    profile_b = _seed_profile(conn, user_id="user-b", sha256="scope-route-sha-b")
    conn.execute(
        """
        INSERT INTO companies (name, normalized_name, stage)
        VALUES (?, ?, ?)
        """,
        ("Dataiku", "dataiku", "growth"),
    )
    company_id = conn.execute("SELECT id FROM companies").fetchone()["id"]
    conn.execute(
        """
        INSERT INTO jobs (
          company_id,
          external_id,
          title,
          source_url,
          content_hash,
          status
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            company_id,
            "dataiku-ml-engineer",
            "Senior ML Engineer",
            "https://boards.greenhouse.io/dataiku/jobs/1",
            "hash-dataiku-1",
            "open",
        ),
    )
    job_id = conn.execute("SELECT id FROM jobs").fetchone()["id"]
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
            profile_a,
            90,
            "Strong fit",
            '["Role and skills fit"]',
            "[]",
            "Prioritize",
            1,
        ),
    )
    conn.commit()

    client = TestClient(app)
    token_a = _make_token("user-a")
    token_b = _make_token("user-b")

    import_a = client.post(
        "/connections/import",
        headers={"Authorization": f"Bearer {token_a}"},
        files={
            "connections_file": (
                "Connections.csv",
                FIXTURE_CSV.read_bytes(),
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    assert import_a.status_code == 303
    assert "import_status=success" in import_a.headers["location"]

    dashboard_b = client.get(
        f"/dashboard?target_profile_id={profile_b}&connection_filter=with_connections",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert dashboard_b.status_code == 200
    assert "Jamie" not in dashboard_b.text

    dashboard_a = client.get(
        f"/dashboard?target_profile_id={profile_a}&connection_filter=with_connections",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert dashboard_a.status_code == 200
    assert "Jamie" in dashboard_a.text