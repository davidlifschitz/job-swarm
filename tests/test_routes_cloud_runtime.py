from fastapi.testclient import TestClient

from ml_job_swarm.app import create_app


def test_cloud_run_api_exposes_durable_run_and_events(tmp_path):
    app = create_app(tmp_path / "cloud-api.db")
    client = TestClient(app)

    created = client.post(
        "/api/cloud/runs",
        json={
            "user_id": "operator-1",
            "requested_action": "refresh_and_prepare",
            "input_manifest": {
                "sources": ["https://jobs.lever.co/acme/123"],
            },
            "idempotency_key": "api-same-request",
            "environment_class": "cloud",
            "code_version": "abc123",
            "container_image_digest": "sha256:runtime",
            "dependency_lock_hash": "lock-hash",
            "feature_flags": {"cloud_runtime": True},
        },
    )
    repeated = client.post(
        "/api/cloud/runs",
        json={
            "user_id": "operator-1",
            "requested_action": "refresh_and_prepare",
            "input_manifest": {
                "sources": ["https://jobs.lever.co/acme/123"],
            },
            "idempotency_key": "api-same-request",
        },
    )

    assert created.status_code == 201
    assert repeated.status_code == 200
    assert repeated.json()["id"] == created.json()["id"]

    run = client.get(f"/api/cloud/runs/{created.json()['id']}")
    assert run.status_code == 200
    assert run.json()["status"] == "queued"
    assert run.json()["events"][0]["event_type"] == "run_created"


def test_cloud_run_api_blocks_sources_and_final_submit_automation(tmp_path):
    app = create_app(tmp_path / "cloud-api.db")
    client = TestClient(app)
    run_id = client.post(
        "/api/cloud/runs",
        json={
            "user_id": "operator-1",
            "requested_action": "refresh_and_prepare",
            "input_manifest": {
                "sources": ["https://www.linkedin.com/jobs/view/1"],
            },
        },
    ).json()["id"]

    policy = client.post(
        f"/api/cloud/runs/{run_id}/sources/evaluate",
        json={"url": "https://www.linkedin.com/jobs/view/1"},
    )
    blocked_submit = client.post(
        f"/api/cloud/runs/{run_id}/final-submit",
        json={
            "packet_id": "packet-1",
            "apply_url": "https://jobs.lever.co/acme/123/apply",
            "requested_by_automation": True,
        },
    )
    manual_instruction = client.post(
        f"/api/cloud/runs/{run_id}/final-submit",
        json={
            "packet_id": "packet-1",
            "apply_url": "https://jobs.lever.co/acme/123/apply",
        },
    )

    assert policy.status_code == 200
    assert policy.json()["mode"] == "blocked"
    assert policy.json()["network_scheduled"] is False
    assert blocked_submit.status_code == 409
    assert blocked_submit.json()["detail"]["manual_final_submit_required"] is True
    assert manual_instruction.status_code == 200
    assert manual_instruction.json()["automation_allowed"] is False
