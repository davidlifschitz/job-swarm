from ml_job_swarm.cloud_runtime import (
    build_runtime_readiness_report,
    cancel_run,
    compare_runtime_parity,
    create_run,
    get_run,
    list_run_events,
    record_prepared_packet,
    record_run_heartbeat,
)
from ml_job_swarm.store import connect, init_db


def test_restart_recovery_preserves_running_state_and_packet_artifacts(tmp_path):
    db_path = tmp_path / "recoverable-cloud.db"
    conn = connect(db_path)
    init_db(conn)
    run = create_run(
        conn,
        user_id="operator-1",
        requested_action="prepare_packet",
        input_manifest={"job_id": 42},
    )
    record_run_heartbeat(conn, run["id"], stage="application_packet")
    record_prepared_packet(
        conn,
        run["id"],
        {
            "packet_id": "packet-42",
            "resume_pdf_path": "/tmp/resume.pdf",
            "source_url": "https://jobs.lever.co/acme/123",
            "decision_id": "decision-42",
            "artifact_checksums": {"resume.pdf": "sha256:abc"},
            "review_status": "prepared",
        },
    )
    conn.close()

    recovered = connect(db_path)
    init_db(recovered)
    persisted = get_run(recovered, run["id"])

    assert persisted["status"] == "prepared"
    assert persisted["current_stage"] == "application_packet"
    assert persisted["last_heartbeat_at"] is not None
    assert persisted["output_manifest"]["prepared_packets"][0]["packet_id"] == "packet-42"
    assert [event["event_type"] for event in list_run_events(recovered, run["id"])] == [
        "run_created",
        "heartbeat",
        "packet_prepared",
    ]


def test_runtime_readiness_report_exposes_operator_truth_and_slo_targets(tmp_path):
    conn = connect(tmp_path / "readiness.db")
    init_db(conn)
    queued = create_run(
        conn,
        user_id="operator-1",
        requested_action="refresh_source",
        input_manifest={"sources": ["https://jobs.lever.co/acme/123"]},
    )
    running = create_run(
        conn,
        user_id="operator-1",
        requested_action="refresh_source",
        input_manifest={"sources": ["https://jobs.lever.co/acme/456"]},
    )
    canceled = create_run(
        conn,
        user_id="operator-1",
        requested_action="refresh_source",
        input_manifest={"sources": ["https://jobs.lever.co/acme/789"]},
    )
    record_run_heartbeat(conn, running["id"], stage="fetching_sources")
    cancel_run(conn, canceled["id"], reason="operator stop")

    report = build_runtime_readiness_report(conn)

    assert report["status"] == "ok"
    assert report["slo_targets"]["health_p95_ms"] == 200
    assert report["slo_targets"]["heartbeat_interval_seconds"] == 15
    assert report["run_counts"]["queued"] == 1
    assert report["run_counts"]["running"] == 1
    assert report["run_counts"]["canceled"] == 1
    assert report["active_run_ids"] == [queued["id"], running["id"]]
    assert report["terminal_run_ids"] == [canceled["id"]]


def test_runtime_parity_report_fails_below_p0_match_rate():
    report = compare_runtime_parity(
        local=[
            {"id": "source-policy", "decision": "allowed"},
            {"id": "fit-bucket", "decision": "strong"},
            {"id": "packet-readiness", "decision": "prepared"},
        ],
        cloud=[
            {"id": "source-policy", "decision": "allowed"},
            {"id": "fit-bucket", "decision": "weak"},
            {"id": "packet-readiness", "decision": "prepared"},
        ],
    )

    assert report["match_rate"] == 2 / 3
    assert report["meets_p0"] is False
    assert report["mismatches"] == [
        {
            "id": "fit-bucket",
            "local_decision": "strong",
            "cloud_decision": "weak",
        }
    ]


def test_cloud_runtime_redacts_sensitive_values_from_client_payloads(tmp_path):
    conn = connect(tmp_path / "redacted.db")
    init_db(conn)
    run = create_run(
        conn,
        user_id="operator-1",
        requested_action="prepare_packet",
        input_manifest={
            "source": "https://jobs.lever.co/acme/123",
            "api_token": "super-secret-token",
        },
    )
    prepared = record_prepared_packet(
        conn,
        run["id"],
        {
            "packet_id": "packet-42",
            "resume_pdf_path": "/tmp/resume.pdf",
            "source_url": "https://jobs.lever.co/acme/123",
            "decision_id": "decision-42",
            "artifact_checksums": {"resume.pdf": "sha256:abc"},
            "review_status": "prepared",
            "private_resume_text": "do not leak this",
        },
    )

    events = list_run_events(conn, run["id"])

    assert get_run(conn, run["id"])["input_manifest"]["api_token"] == "[redacted]"
    assert prepared["output_manifest"]["prepared_packets"][0]["private_resume_text"] == (
        "[redacted]"
    )
    assert events[-1]["payload"]["private_resume_text"] == "[redacted]"
