import time

import jwt
from fastapi.testclient import TestClient

from ml_job_swarm.app import create_app
from ml_job_swarm.profile import create_target_profile

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


def _seed_profile(conn, *, user_id: str, sha256: str) -> tuple[int, int]:
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
        (user_id, "resume.pdf", "application/pdf", "/tmp/resume.pdf", sha256),
    ).lastrowid
    profile_id = create_target_profile(
        conn,
        resume_asset_id=resume_asset_id,
        keywords=KEYWORDS,
        preferences=PREFERENCES,
        user_id=user_id,
    )
    return resume_asset_id, profile_id


def test_authenticated_users_cannot_access_other_users_resume_assets(tmp_path, monkeypatch):
    _auth_env(monkeypatch)
    app = create_app(tmp_path / "resume-scope.db")
    conn = app.state.conn
    asset_a, _ = _seed_profile(conn, user_id="user-a", sha256="resume-sha-a")
    asset_b, _ = _seed_profile(conn, user_id="user-b", sha256="resume-sha-b")
    conn.commit()

    client = TestClient(app)
    token_a = _make_token("user-a")
    token_b = _make_token("user-b")

    denied = client.get(
        f"/onboarding?resume_asset_id={asset_b}",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert denied.status_code == 403

    allowed = client.get(
        f"/onboarding?resume_asset_id={asset_a}",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert allowed.status_code == 200

    api_denied = client.get(
        f"/api/v1/onboarding?resume_asset_id={asset_b}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert api_denied.status_code == 200
    assert api_denied.json()["resume_asset_id"] == asset_b

    api_other = client.get(
        f"/api/v1/onboarding?resume_asset_id={asset_b}",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert api_other.status_code == 403


def test_resume_upload_dedupes_per_user_not_globally(tmp_path, monkeypatch):
    _auth_env(monkeypatch)
    app = create_app(tmp_path / "resume-dedupe.db")
    client = TestClient(app)
    token_a = _make_token("user-a")
    token_b = _make_token("user-b")

    pdf_bytes = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
    upload_a = client.post(
        "/api/v1/onboarding/resume",
        headers={"Authorization": f"Bearer {token_a}"},
        files={"resume": ("resume.pdf", pdf_bytes, "application/pdf")},
    )
    upload_b = client.post(
        "/api/v1/onboarding/resume",
        headers={"Authorization": f"Bearer {token_b}"},
        files={"resume": ("resume.pdf", pdf_bytes, "application/pdf")},
    )
    assert upload_a.status_code == 200
    assert upload_b.status_code == 200
    assert upload_a.json()["resume_asset_id"] != upload_b.json()["resume_asset_id"]

    conn = app.state.conn
    assert conn.execute("SELECT COUNT(*) FROM resume_assets").fetchone()[0] == 2