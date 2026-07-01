from fastapi.testclient import TestClient

from ml_job_swarm.app import create_app
from ml_job_swarm.cloud_runtime import create_run
from ml_job_swarm.ingest import RawJob
from tests.support.cloud_load_seed import seed_saved_packet_job


class FakeAdapter:
    def fetch_jobs(self, source):
        return [
            RawJob(
                external_id="cloud-1",
                title="Senior Machine Learning Engineer",
                location_text="Remote",
                remote_mode="remote",
                seniority="senior",
                description_text="Cloud worker route test.",
                requirements_text="Python and ML.",
                apply_url="https://jobs.lever.co/acme/cloud-1/apply",
                source_url=source.url,
            )
        ]


def test_cloud_worker_route_executes_next_queued_run(tmp_path):
    app = create_app(tmp_path / "cloud-worker-route.db")
    app.state.adapter_registry._adapters["lever"] = FakeAdapter()
    conn = app.state.conn
    source_id, profile_id = _seed_cloud_route_catalog(conn)
    run = create_run(
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
    client = TestClient(app)

    response = client.post("/api/cloud/worker/run-next")
    run_response = client.get(f"/api/cloud/runs/{run['id']}")

    assert response.status_code == 200
    assert response.json()["run_id"] == run["id"]
    assert response.json()["status"] == "waiting_for_user"
    assert run_response.json()["next_action"] == "manual_final_submit"
    assert run_response.json()["events"][-1]["event_type"] == (
        "manual_final_submit_required"
    )


def _seed_cloud_route_catalog(conn):
    company_id = conn.execute(
        """
        INSERT INTO companies (name, normalized_name, ats_type, source_quality)
        VALUES ('Acme Route', 'acme route', 'lever', 'reviewed')
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
        VALUES (?, 'https://jobs.lever.co/acme-route', 'lever', 'allowed', 'approved')
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
        VALUES ('resume.pdf', 'application/pdf', '/tmp/route-resume.pdf', 'sha256-route')
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
        VALUES (
          ?,
          'Route profile',
          '["Machine Learning Engineer"]',
          '["senior"]',
          '["Remote"]',
          '["remote"]'
        )
        RETURNING id
        """,
        (resume_asset_id,),
    ).fetchone()["id"]
    seed_saved_packet_job(
        conn,
        company_id=int(company_id),
        source_id=int(source_id),
        profile_id=int(profile_id),
        external_id="cloud-1",
        apply_url="https://jobs.lever.co/acme/cloud-1/apply",
        source_url="https://jobs.lever.co/acme",
    )
    return source_id, profile_id
