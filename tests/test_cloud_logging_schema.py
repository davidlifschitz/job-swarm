import json
import logging

import pytest

from ml_job_swarm.cloud_logging import (
    build_transition_log,
    validate_transition_log,
)
from ml_job_swarm.cloud_runtime import cancel_run, create_run, fail_run
from ml_job_swarm.store import connect, init_db


@pytest.fixture()
def conn(tmp_path):
    db = connect(tmp_path / "cloud-logging-schema.db")
    init_db(db)
    return db


def _cloud_transition_logs(caplog: pytest.LogCaptureFixture) -> list[dict[str, object]]:
    logs: list[dict[str, object]] = []
    for record in caplog.records:
        if record.name != "ml_job_swarm.cloud" or record.levelno < logging.INFO:
            continue
        logs.append(json.loads(record.getMessage()))
    return logs


def test_build_transition_log_contains_required_fields():
    log = build_transition_log(
        run_id="run_abc",
        stage="queued",
        trace_id="trace_abc",
        duration_ms=0,
        event_type="run_created",
        status="queued",
    )

    assert log == {
        "run_id": "run_abc",
        "stage": "queued",
        "trace_id": "trace_abc",
        "duration_ms": 0,
        "event_type": "run_created",
        "status": "queued",
    }
    assert validate_transition_log(log) == []


def test_validate_transition_log_reports_missing_and_invalid_fields():
    violations = validate_transition_log({})

    assert "missing required field: run_id" in violations
    assert "missing required field: stage" in violations
    assert "missing required field: trace_id" in violations
    assert "missing required field: duration_ms" in violations
    assert "missing required field: event_type" in violations
    assert "missing required field: status" in violations

    invalid = build_transition_log(
        run_id="",
        stage="",
        trace_id="",
        duration_ms=-1,
        event_type="",
        status="unknown",
    )
    invalid_violations = validate_transition_log(invalid)

    assert "run_id must be a non-empty string" in invalid_violations
    assert "stage must be a non-empty string" in invalid_violations
    assert "trace_id must be a non-empty string" in invalid_violations
    assert "duration_ms must be non-negative" in invalid_violations
    assert "event_type must be a non-empty string" in invalid_violations
    assert any("status must be one of" in item for item in invalid_violations)


def test_create_run_emits_schema_valid_transition_logs(conn, caplog):
    with caplog.at_level(logging.INFO, logger="ml_job_swarm.cloud"):
        run = create_run(
            conn,
            user_id="operator-1",
            requested_action="refresh_source",
            input_manifest={"sources": ["https://jobs.lever.co/acme/123"]},
        )

    logs = _cloud_transition_logs(caplog)
    assert logs
    assert all(validate_transition_log(log) == [] for log in logs)
    assert logs[-1]["event_type"] == "run_created"
    assert logs[-1]["run_id"] == run["id"]
    assert logs[-1]["trace_id"] == run["trace_id"]
    assert logs[-1]["status"] == "queued"
    assert logs[-1]["stage"] == "queued"


def test_cancel_run_emits_schema_valid_transition_logs(conn, caplog):
    run = create_run(
        conn,
        user_id="operator-1",
        requested_action="refresh_source",
        input_manifest={"sources": ["https://jobs.lever.co/acme/123"]},
    )
    caplog.clear()

    with caplog.at_level(logging.INFO, logger="ml_job_swarm.cloud"):
        cancel_run(conn, run["id"], reason="operator requested stop")

    logs = _cloud_transition_logs(caplog)
    assert logs
    assert all(validate_transition_log(log) == [] for log in logs)
    assert {log["event_type"] for log in logs} == {"state_transition", "run_canceled"}
    assert all(log["run_id"] == run["id"] for log in logs)
    assert all(log["trace_id"] == run["trace_id"] for log in logs)
    assert all(log["status"] == "canceled" for log in logs)
    assert all(log["stage"] == "canceled" for log in logs)


def test_fail_run_emits_schema_valid_transition_logs(conn, caplog):
    run = create_run(
        conn,
        user_id="operator-1",
        requested_action="refresh_source",
        input_manifest={"sources": ["https://jobs.lever.co/acme/123"]},
    )
    caplog.clear()

    with caplog.at_level(logging.INFO, logger="ml_job_swarm.cloud"):
        fail_run(
            conn,
            run["id"],
            error_code="cloud_worker_failed",
            error_message="simulated worker failure",
        )

    logs = _cloud_transition_logs(caplog)
    assert logs
    assert all(validate_transition_log(log) == [] for log in logs)
    assert {log["event_type"] for log in logs} == {"state_transition", "run_failed"}
    assert all(log["run_id"] == run["id"] for log in logs)
    assert all(log["trace_id"] == run["trace_id"] for log in logs)
    assert all(log["status"] == "failed" for log in logs)
    assert all(log["stage"] == "failed" for log in logs)
