from fastapi.testclient import TestClient

from ml_job_swarm.app import create_app


def test_healthz_and_cloud_readiness_routes_expose_operator_state(tmp_path):
    app = create_app(tmp_path / "cloud-readiness-api.db")
    client = TestClient(app)

    created = client.post(
        "/api/cloud/runs",
        json={
            "user_id": "operator-1",
            "requested_action": "refresh_source",
            "input_manifest": {"sources": ["https://jobs.lever.co/acme/123"]},
        },
    ).json()
    client.post(
        f"/api/cloud/runs/{created['id']}/heartbeat",
        json={"stage": "fetching_sources"},
    )

    health = client.get("/healthz")
    readiness = client.get("/api/cloud/readiness")
    runs = client.get("/api/cloud/runs")

    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert health.json()["service"] == "ml-job-swarm"
    assert health.json()["database"] == "ok"
    assert health.json()["slo_targets"]["health_p95_ms"] == 200
    assert readiness.status_code == 200
    assert readiness.json()["run_counts"]["running"] == 1
    assert readiness.json()["active_run_ids"] == [created["id"]]
    assert runs.status_code == 200
    assert runs.json()["runs"][0]["id"] == created["id"]
    assert runs.json()["runs"][0]["events"][0]["event_type"] == "run_created"
