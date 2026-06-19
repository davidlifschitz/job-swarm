import pytest

from ml_job_swarm.cloud_runtime import (
    ManualFinalSubmitBlocked,
    cancel_run,
    create_run,
    create_manual_final_submit_instruction,
    evaluate_source_for_run,
    get_run,
    list_run_events,
    record_prepared_packet,
    record_run_heartbeat,
)
from ml_job_swarm.store import connect, init_db


@pytest.fixture()
def conn(tmp_path):
    db = connect(tmp_path / "cloud-runtime.db")
    init_db(db)
    return db


def test_create_run_persists_reproducible_lifecycle_state_and_is_idempotent(conn):
    first = create_run(
        conn,
        user_id="operator-1",
        requested_action="refresh_and_prepare",
        input_manifest={"sources": ["https://jobs.lever.co/acme/123"]},
        idempotency_key="same-request",
        environment_class="cloud",
        code_version="abc123",
        container_image_digest="sha256:runtime",
        dependency_lock_hash="lock-hash",
        feature_flags={"cloud_runtime": True},
    )
    second = create_run(
        conn,
        user_id="operator-1",
        requested_action="refresh_and_prepare",
        input_manifest={"sources": ["https://jobs.lever.co/acme/123"]},
        idempotency_key="same-request",
        environment_class="cloud",
        code_version="abc123",
        container_image_digest="sha256:runtime",
        dependency_lock_hash="lock-hash",
        feature_flags={"cloud_runtime": True},
    )

    assert second["id"] == first["id"]
    assert first["status"] == "queued"
    assert first["current_stage"] == "queued"
    assert first["trace_id"]
    assert first["source_policy_version"]
    assert first["environment_class"] == "cloud"
    assert first["code_version"] == "abc123"
    assert first["container_image_digest"] == "sha256:runtime"
    assert first["dependency_lock_hash"] == "lock-hash"
    assert first["feature_flags"] == {"cloud_runtime": True}

    persisted = get_run(conn, first["id"])
    assert persisted["input_manifest"] == {
        "sources": ["https://jobs.lever.co/acme/123"]
    }
    assert [event["event_type"] for event in list_run_events(conn, first["id"])] == [
        "run_created"
    ]


def test_blocked_source_records_policy_denial_without_scheduling_network_work(conn):
    run = create_run(
        conn,
        user_id="operator-1",
        requested_action="refresh_source",
        input_manifest={"sources": ["https://www.linkedin.com/jobs/view/1"]},
    )

    result = evaluate_source_for_run(
        conn,
        run["id"],
        "https://www.linkedin.com/jobs/view/1",
    )

    assert result["mode"] == "blocked"
    assert result["network_scheduled"] is False
    assert result["next_action"] == "provide_allowed_employer_or_ats_source"
    assert get_run(conn, run["id"])["status"] == "waiting_for_user"
    assert list_run_events(conn, run["id"])[-1]["event_type"] == "source_policy_denied"


def test_prepared_packet_requires_manifest_fields_and_moves_to_manual_submit(conn):
    run = create_run(
        conn,
        user_id="operator-1",
        requested_action="prepare_packet",
        input_manifest={"job_id": 42},
    )

    with pytest.raises(ValueError, match="resume_pdf_path"):
        record_prepared_packet(conn, run["id"], {"source_url": "https://jobs.lever.co/acme/123"})

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
        },
    )

    assert prepared["status"] == "prepared"
    assert prepared["next_action"] == "manual_final_submit"
    assert prepared["output_manifest"]["prepared_packets"][0]["packet_id"] == "packet-42"


def test_cloud_runtime_blocks_automated_final_submit_and_records_manual_instruction(conn):
    run = create_run(
        conn,
        user_id="operator-1",
        requested_action="prepare_packet",
        input_manifest={"job_id": 42},
    )

    with pytest.raises(ManualFinalSubmitBlocked):
        create_manual_final_submit_instruction(
            conn,
            run["id"],
            packet_id="packet-42",
            apply_url="https://jobs.lever.co/acme/123/apply",
            requested_by_automation=True,
        )

    instruction = create_manual_final_submit_instruction(
        conn,
        run["id"],
        packet_id="packet-42",
        apply_url="https://jobs.lever.co/acme/123/apply",
    )

    assert instruction["automation_allowed"] is False
    assert instruction["manual_final_submit_required"] is True
    assert get_run(conn, run["id"])["status"] == "waiting_for_user"
    assert list_run_events(conn, run["id"])[-1]["event_type"] == (
        "manual_final_submit_required"
    )


def test_heartbeat_and_cancel_are_persisted_as_observable_state(conn):
    run = create_run(
        conn,
        user_id="operator-1",
        requested_action="refresh_source",
        input_manifest={"sources": ["https://jobs.lever.co/acme/123"]},
    )

    running = record_run_heartbeat(conn, run["id"], stage="fetching_sources")
    canceled = cancel_run(conn, run["id"], reason="operator requested stop")

    assert running["status"] == "running"
    assert running["current_stage"] == "fetching_sources"
    assert running["last_heartbeat_at"] is not None
    assert canceled["status"] == "canceled"
    assert canceled["current_stage"] == "canceled"
    assert canceled["completed_at"] is not None
    assert [event["event_type"] for event in list_run_events(conn, run["id"])] == [
        "run_created",
        "heartbeat",
        "run_canceled",
    ]
