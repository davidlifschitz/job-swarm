import time

import jwt
from fastapi.testclient import TestClient

from ml_job_swarm.app import create_app
from ml_job_swarm.auth_middleware import ACCESS_TOKEN_COOKIE
from ml_job_swarm.supabase_auth import supabase_config_from_env, validate_access_token

JWT_SECRET = "test-jwt-secret-for-hosted-auth-32b"


def _make_token(subject: str = "user-abc", *, expired: bool = False) -> str:
    now = int(time.time())
    payload = {
        "sub": subject,
        "aud": "authenticated",
        "exp": now - 10 if expired else now + 3600,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def _auth_env(monkeypatch) -> None:
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-test-key")
    monkeypatch.setenv("SUPABASE_JWT_SECRET", JWT_SECRET)


def test_supabase_config_from_env_requires_all_values():
    assert supabase_config_from_env({}) is None
    assert (
        supabase_config_from_env(
            {
                "SUPABASE_URL": "https://example.supabase.co",
                "SUPABASE_ANON_KEY": "anon",
            }
        )
        is None
    )


def test_validate_access_token_accepts_authenticated_audience():
    config = supabase_config_from_env(
        {
            "SUPABASE_URL": "https://example.supabase.co",
            "SUPABASE_ANON_KEY": "anon",
            "SUPABASE_JWT_SECRET": JWT_SECRET,
        }
    )
    assert config is not None
    claims = validate_access_token(_make_token("user-123"), config)
    assert claims["sub"] == "user-123"


def test_supabase_auth_middleware_blocks_dashboard_without_token(tmp_path, monkeypatch):
    _auth_env(monkeypatch)
    client = TestClient(create_app(tmp_path / "auth.db"))

    assert client.get("/healthz").status_code == 200
    blocked = client.get("/dashboard", follow_redirects=False)
    assert blocked.status_code == 303
    assert blocked.headers["location"].startswith("/auth/login")


def test_supabase_auth_middleware_accepts_bearer_and_cookie(tmp_path, monkeypatch):
    _auth_env(monkeypatch)
    client = TestClient(create_app(tmp_path / "auth-bearer.db"))
    token = _make_token("operator-9")

    bearer = client.get("/dashboard", headers={"Authorization": f"Bearer {token}"})
    assert bearer.status_code == 200

    client_cookie = TestClient(create_app(tmp_path / "auth-cookie.db"))
    client_cookie.cookies.set(ACCESS_TOKEN_COOKIE, token)
    cookie = client_cookie.get("/dashboard")
    assert cookie.status_code == 200


def test_cloud_runs_are_scoped_to_authenticated_user(tmp_path, monkeypatch):
    _auth_env(monkeypatch)
    client = TestClient(create_app(tmp_path / "auth-cloud.db"))
    token_a = _make_token("user-a")
    token_b = _make_token("user-b")
    headers_a = {"Authorization": f"Bearer {token_a}"}

    created = client.post(
        "/api/cloud/runs",
        headers=headers_a,
        json={
            "requested_action": "refresh_source",
            "input_manifest": {"sources": ["https://jobs.lever.co/acme/123"]},
        },
    )
    assert created.status_code == 201
    assert created.json()["user_id"] == "user-a"

    mismatch = client.post(
        "/api/cloud/runs",
        headers=headers_a,
        json={
            "user_id": "user-b",
            "requested_action": "refresh_source",
            "input_manifest": {"sources": ["https://jobs.lever.co/acme/123"]},
        },
    )
    assert mismatch.status_code == 403

    listed = client.get("/api/cloud/runs", headers=headers_a).json()["runs"]
    assert len(listed) == 1

    other_user = client.get("/api/cloud/runs", headers={"Authorization": f"Bearer {token_b}"})
    assert other_user.json()["runs"] == []


def test_auth_callback_sets_session_cookie(tmp_path, monkeypatch):
    _auth_env(monkeypatch)
    client = TestClient(create_app(tmp_path / "auth-callback.db"))
    token = _make_token("callback-user")

    response = client.post("/auth/callback", json={"access_token": token})

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert ACCESS_TOKEN_COOKIE in response.cookies