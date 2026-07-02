import json

from ml_job_swarm.cloud_runtime import create_run, get_run, list_run_events
from ml_job_swarm.cloud_worker import run_cloud_workflow_once
from ml_job_swarm.ingest import AdapterRegistry, RawJob
from ml_job_swarm.store import connect, init_db


class FakeLeverAdapter:
    def fetch_jobs(self, source):
        return [
            RawJob(
                external_id="ml-1",
                title="Senior Machine Learning Engineer",
                location_text="Remote",
                remote_mode="remote",
                seniority="senior",
                description_text="Build ML systems and production agents.",
                requirements_text="Python, ML, production systems.",
                apply_url="https://jobs.lever.co/acme/ml-1/apply",
                source_url=source.url,
            )
        ]


def test_cloud_worker_refreshes_matches_prepares_packet_and_stops_for_manual_submit(tmp_path):
    conn = connect(tmp_path / "cloud-worker.db")
    init_db(conn)
    source_id, profile_id = _seed_cloud_ready_catalog(conn, saved_packet_candidate=True)
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

    result = run_cloud_workflow_once(
        conn,
        adapter_registry=AdapterRegistry({"lever": FakeLeverAdapter()}),
    )

    updated = get_run(conn, run["id"])
    events = [event["event_type"] for event in list_run_events(conn, run["id"])]
    app_packet = conn.execute("SELECT * FROM application_packets").fetchone()

    assert result["run_id"] == run["id"]
    assert result["status"] == "waiting_for_user"
    assert updated["status"] == "waiting_for_user"
    assert updated["next_action"] == "manual_final_submit"
    assert updated["output_manifest"]["refresh"]["sources_attempted"] == 1
    assert updated["output_manifest"]["matching"]["rules_preview_count"] == 1
    assert updated["output_manifest"]["prepared_packets"][0]["packet_id"] == str(
        app_packet["id"]
    )
    assert app_packet["status"] == "prepared"
    assert "heartbeat" in events
    assert "packet_prepared" in events
    assert events[-1] == "manual_final_submit_required"


def test_cloud_worker_blocks_restricted_sources_before_network_work(tmp_path):
    conn = connect(tmp_path / "cloud-worker-blocked.db")
    init_db(conn)
    create_run(
        conn,
        user_id="operator-1",
        requested_action="continue_local_workflow",
        input_manifest={
            "sources": ["https://www.linkedin.com/jobs/view/123"],
        },
        environment_class="cloud",
    )

    result = run_cloud_workflow_once(
        conn,
        adapter_registry=AdapterRegistry({"lever": FakeLeverAdapter()}),
    )

    assert result["status"] == "waiting_for_user"
    assert result["next_action"] == "provide_allowed_employer_or_ats_source"
    assert conn.execute("SELECT COUNT(*) AS count FROM jobs").fetchone()["count"] == 0


def test_cloud_worker_marks_run_failed_with_diagnostic_event(tmp_path):
    conn = connect(tmp_path / "cloud-worker-failed.db")
    init_db(conn)
    create_run(
        conn,
        user_id="operator-1",
        requested_action="continue_local_workflow",
        input_manifest={
            "source_ids": [999],
            "target_profile_id": 123,
        },
        environment_class="cloud",
    )

    result = run_cloud_workflow_once(
        conn,
        adapter_registry=AdapterRegistry({"lever": FakeLeverAdapter()}),
    )

    assert result["status"] == "failed"
    assert result["error_code"] == "cloud_worker_failed"
    assert list_run_events(conn, result["run_id"])[-1]["event_type"] == "run_failed"


def test_cloud_worker_records_llm_skipped_when_client_missing(tmp_path):
    conn = connect(tmp_path / "cloud-worker-llm-skipped.db")
    init_db(conn)
    source_id, profile_id = _seed_cloud_ready_catalog(conn)
    create_run(
        conn,
        user_id="operator-1",
        requested_action="continue_local_workflow",
        input_manifest={
            "source_ids": [source_id],
            "target_profile_id": profile_id,
            "review_jobs_with_llm": True,
        },
        environment_class="cloud",
    )

    result = run_cloud_workflow_once(
        conn,
        adapter_registry=AdapterRegistry({"lever": FakeLeverAdapter()}),
        fit_gate_client=None,
    )

    updated = get_run(conn, result["run_id"])
    matching = updated["output_manifest"]["matching"]
    assert matching["mode"] == "llm_skipped"
    assert matching["reason"] == "fit_gate_client_unavailable"
    assert matching["failures"] == 0


def test_cloud_worker_packet_candidates_require_saved_decision(tmp_path):
    conn = connect(tmp_path / "cloud-worker-saved-only.db")
    init_db(conn)
    source_id, profile_id = _seed_cloud_ready_catalog(conn)
    create_run(
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

    result = run_cloud_workflow_once(
        conn,
        adapter_registry=AdapterRegistry({"lever": FakeLeverAdapter()}),
    )

    updated = get_run(conn, result["run_id"])
    assert result["status"] == "completed"
    assert updated["output_manifest"].get("prepared_packets") in (None, [])
    assert conn.execute("SELECT COUNT(*) AS count FROM application_packets").fetchone()["count"] == 0


def _seed_cloud_ready_catalog(conn, *, saved_packet_candidate: bool = False):
    company_id = conn.execute(
        """
        INSERT INTO companies (name, normalized_name, ats_type, source_quality)
        VALUES ('Acme AI', 'acme ai', 'lever', 'reviewed')
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
        VALUES (?, 'https://jobs.lever.co/acme', 'lever', 'allowed', 'approved')
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
        VALUES ('resume.pdf', 'application/pdf', '/tmp/resume.pdf', 'sha256-resume')
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
        VALUES (?, 'Cloud profile', ?, ?, ?, ?)
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
    job_id = conn.execute(
        """
        INSERT INTO jobs (
          company_id,
          job_source_id,
          external_id,
          title,
          location_text,
          remote_mode,
          seniority,
          description_text,
          requirements_text,
          apply_url,
          source_url,
          content_hash,
          status
        )
        VALUES (?, ?, 'ml-1', 'Senior Machine Learning Engineer', 'Remote', 'remote', 'senior',
                'Build ML systems.', 'Python.', 'https://jobs.lever.co/acme/ml-1/apply',
                'https://jobs.lever.co/acme', 'cloud-worker-hash', 'open')
        RETURNING id
        """,
        (company_id, source_id),
    ).fetchone()["id"]
    if saved_packet_candidate:
        conn.execute(
            """
            INSERT INTO job_decisions (job_id, target_profile_id, decision, notes)
            VALUES (?, ?, 'saved', 'cloud worker packet candidate')
            """,
            (job_id, profile_id),
        )
    conn.commit()
    return source_id, profile_id
