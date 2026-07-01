import json

from fastapi.testclient import TestClient

from ml_job_swarm.app import create_app
from ml_job_swarm.cloud_runtime import create_run, get_run
from ml_job_swarm.cloud_worker import run_cloud_worker_loop
from ml_job_swarm.ingest import AdapterRegistry, RawJob
from ml_job_swarm.store import connect, init_db
from tests.support.cloud_load_seed import seed_saved_packet_job


class FakeAdapter:
    def fetch_jobs(self, source):
        return [
            RawJob(
                external_id=f"{source.id}-cloud",
                title="Senior Machine Learning Engineer",
                location_text="Remote",
                remote_mode="remote",
                seniority="senior",
                description_text="Cloud worker loop test.",
                requirements_text="Python, ML, cloud runtime.",
                apply_url=f"{source.url}/cloud/apply",
                source_url=source.url,
            )
        ]


def test_cloud_worker_loop_drains_queued_runs_until_idle(tmp_path):
    conn = connect(tmp_path / "cloud-worker-loop.db")
    init_db(conn)
    source_id, profile_id = _seed_cloud_loop_catalog(conn)
    first = create_run(
        conn,
        user_id="operator-1",
        requested_action="continue_local_workflow",
        input_manifest={
            "source_ids": [source_id],
            "target_profile_id": profile_id,
            "prepare_packets": True,
            "max_packets": 1,
        },
        environment_class="cloud",
    )
    second = create_run(
        conn,
        user_id="operator-1",
        requested_action="continue_local_workflow",
        input_manifest={},
        environment_class="cloud",
    )

    summary = run_cloud_worker_loop(
        conn,
        adapter_registry=AdapterRegistry({"lever": FakeAdapter()}),
        max_runs=5,
    )

    assert summary["runs_processed"] == 2
    assert summary["idle"] is True
    assert get_run(conn, first["id"])["status"] == "waiting_for_user"
    assert get_run(conn, second["id"])["status"] == "completed"


def test_cloud_execute_route_creates_and_runs_workflow(tmp_path):
    app = create_app(tmp_path / "cloud-execute-route.db")
    app.state.adapter_registry._adapters["lever"] = FakeAdapter()
    conn = app.state.conn
    source_id, profile_id = _seed_cloud_loop_catalog(conn)
    client = TestClient(app)

    response = client.post(
        "/api/cloud/workflows/continue",
        json={
            "user_id": "operator-1",
            "input_manifest": {
                "source_ids": [source_id],
                "target_profile_id": profile_id,
                "prepare_packets": True,
                "max_packets": 1,
            },
            "idempotency_key": "execute-now",
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "waiting_for_user"
    assert response.json()["next_action"] == "manual_final_submit"
    assert response.json()["output_manifest"]["refresh"]["sources_attempted"] == 1


def _seed_cloud_loop_catalog(conn):
    company_id = conn.execute(
        """
        INSERT INTO companies (name, normalized_name, ats_type, source_quality)
        VALUES ('Cloud Loop Co', 'cloud loop co', 'lever', 'reviewed')
        RETURNING id
        """
    ).fetchone()["id"]
    source_id = conn.execute(
        """
        INSERT INTO job_sources (
          company_id,
          url,
          source_type,
          policy_mode,
          review_status
        )
        VALUES (?, 'https://jobs.lever.co/cloud-loop', 'lever', 'allowed', 'approved')
        RETURNING id
        """,
        (company_id,),
    ).fetchone()["id"]
    resume_asset_id = conn.execute(
        """
        INSERT INTO resume_assets (
          original_filename,
          content_type,
          storage_path,
          sha256
        )
        VALUES ('resume.pdf', 'application/pdf', '/tmp/cloud-loop-resume.pdf', 'sha256-loop')
        RETURNING id
        """
    ).fetchone()["id"]
    profile_id = conn.execute(
        """
        INSERT INTO target_profiles (
          resume_asset_id,
          name,
          desired_titles_json,
          levels_json,
          locations_json,
          remote_modes_json
        )
        VALUES (?, 'Loop profile', ?, ?, ?, ?)
        RETURNING id
        """,
        (
            resume_asset_id,
            json.dumps(["Machine Learning Engineer"]),
            json.dumps(["senior"]),
            json.dumps(["Remote"]),
            json.dumps(["remote"]),
        ),
    ).fetchone()["id"]
    seed_saved_packet_job(
        conn,
        company_id=int(company_id),
        source_id=int(source_id),
        profile_id=int(profile_id),
        external_id=f"{source_id}-cloud",
        apply_url="https://jobs.lever.co/cloud-loop/cloud/apply",
        source_url="https://jobs.lever.co/cloud-loop",
    )
    return source_id, profile_id
