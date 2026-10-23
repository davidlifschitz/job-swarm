from __future__ import annotations

import io
import json
import time
from email.message import Message

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


@pytest.fixture
def greenhouse_bulk_response(monkeypatch):
    """A valid unpaginated board larger than 5 MiB; fake only outbound HTTP."""
    from ml_job_swarm import adapters

    jobs = [
        {
            "id": index,
            "internal_job_id": index,
            "title": "Senior Machine Learning Engineer",
            "updated_at": "2026-10-21T10:00:00Z",
            "requisition_id": str(index),
            "location": {"name": "Remote US"},
            "absolute_url": f"https://boards.greenhouse.io/example/jobs/{index}",
            "language": "en",
            "metadata": [],
            "content": (
                "<p>Build production ML systems with Python. "
                + "Public job description. " * 700 + "</p>"
            ),
            "departments": [{"id": 1, "name": "Engineering"}],
            "offices": [],
        }
        for index in range(1, 401)
    ]
    body = json.dumps({"jobs": jobs, "meta": {"total": 400}}).encode()
    assert 5 * 1024 * 1024 < len(body) < 32 * 1024 * 1024

    class FixtureOpener:
        def open(self, request, timeout=20):
            assert request.full_url == (
                "https://boards-api.greenhouse.io/v1/boards/example/jobs?content=true"
            ), f"Unexpected outbound request: {request.full_url}"
            response = io.BytesIO(body)
            response.headers = Message()
            response.headers["Content-Type"] = "application/json; charset=utf-8"
            return response

    monkeypatch.setattr(adapters, "_build_safe_fetch_opener", FixtureOpener)
    return body
