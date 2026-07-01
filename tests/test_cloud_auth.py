from fastapi.testclient import TestClient

from ml_job_swarm.app import create_app
from ml_job_swarm.cloud_auth import SERVICE_TOKEN_HEADER
from tests.conftest import auth_env, auth_headers


def test_cloud_worker_requires_auth_when_supabase_enabled(tmp_path, auth_env):
    client = TestClient(create_app(tmp_path / "cloud-auth-required.db"))

    blocked = client.post("/api/cloud/worker/run-next")
    assert blocked.status_code == 401


def test_cloud_worker_accepts_service_token(tmp_path, auth_env, monkeypatch):
    monkeypatch.setenv("ML_JOB_SWARM_CLOUD_SERVICE_TOKEN", "worker-secret")
    client = TestClient(create_app(tmp_path / "cloud-service-token.db"))

    response = client.post(
        "/api/cloud/worker/run-next",
        headers={SERVICE_TOKEN_HEADER: "worker-secret"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "idle"


def test_cloud_runs_require_auth_when_supabase_enabled(tmp_path, auth_env):
    client = TestClient(create_app(tmp_path / "cloud-runs-auth.db"))

    blocked = client.get("/api/cloud/runs")
    assert blocked.status_code == 401

    allowed = client.get("/api/cloud/runs", headers=auth_headers("user-a"))
    assert allowed.status_code == 200
