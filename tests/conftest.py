from __future__ import annotations

import time

import jwt
import pytest

JWT_SECRET = "test-jwt-secret-for-hosted-auth-32b"


@pytest.fixture
def auth_env(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-test-key")
    monkeypatch.setenv("SUPABASE_JWT_SECRET", JWT_SECRET)


@pytest.fixture
def admin_auth_env(auth_env, monkeypatch):
    monkeypatch.setenv("ML_JOB_SWARM_ADMIN_USER_IDS", "admin-user,ops-user")


def make_token(subject: str = "user-abc", *, expired: bool = False) -> str:
    now = int(time.time())
    payload = {
        "sub": subject,
        "aud": "authenticated",
        "exp": now - 10 if expired else now + 3600,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def auth_headers(subject: str = "user-abc") -> dict[str, str]:
    return {"Authorization": f"Bearer {make_token(subject)}"}
