from __future__ import annotations

import json
import sqlite3
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from ml_job_swarm.db.protocol import Database

StoreConnection = sqlite3.Connection | Database

CLOUD_RUN_QUEUE_ORDER = "created_at ASC, id ASC"

from ml_job_swarm.source_policy import SourcePolicyResult, classify_source_url

SOURCE_POLICY_VERSION = "source-policy-v1"
SLO_TARGETS = {
    "health_p95_ms": 200,
    "health_p99_ms": 500,
    "heartbeat_interval_seconds": 15,
    "first_progress_p95_seconds": 10,
    "restart_recovery_seconds": 60,
    "rpo_minutes": 5,
    "rto_minutes": 15,
    "manual_final_submit_automation_allowed": 0,
}

RUN_STATUSES = {
    "queued",
    "running",
    "waiting_for_user",
    "prepared",
    "failed",
    "canceled",
    "completed",
}
TERMINAL_STATUSES = {"failed", "canceled", "completed"}
REQUIRED_PACKET_MANIFEST_FIELDS = {
    "resume_pdf_path",
    "source_url",
    "decision_id",
    "artifact_checksums",
    "review_status",
}
SENSITIVE_KEY_TERMS = (
    "authorization",
    "browser_profile",
    "cookie",
    "key",
    "password",
    "private",
    "prompt",
    "resume_text",
    "secret",
    "session",
    "token",
)


class CloudRuntimeError(RuntimeError):
    pass


class RunNotFound(CloudRuntimeError):
    pass


class InvalidRunTransition(CloudRuntimeError):
    pass


class ManualFinalSubmitBlocked(CloudRuntimeError):
    def __init__(self, instruction: dict[str, object]) -> None:
        super().__init__("cloud runtime cannot automate final submit")
        self.instruction = instruction


def create_run(
    conn: StoreConnection,
    *,
    user_id: str,
    requested_action: str,
    input_manifest: dict[str, object],
    idempotency_key: str | None = None,
    environment_class: str = "local",
    code_version: str = "unknown",
    container_image_digest: str = "unknown",
    dependency_lock_hash: str = "unknown",
    feature_flags: dict[str, object] | None = None,
) -> dict[str, object]:
    existing = find_run_by_idempotency_key(conn, user_id, idempotency_key)
    if existing is not None:
        return existing

    now = _now()
    run_id = f"run_{uuid4().hex}"
    trace_id = f"trace_{uuid4().hex}"
    conn.execute(
        """
        INSERT INTO cloud_runs (
          id,
          user_id,
          requested_action,
          status,
          current_stage,
          input_manifest_json,
          output_manifest_json,
          idempotency_key,
          trace_id,
          code_version,
          container_image_digest,
          dependency_lock_hash,
          environment_class,
          feature_flags_json,
          source_policy_version,
          created_at,
          updated_at
        )
        VALUES (?, ?, ?, 'queued', 'queued', ?, '{}', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id,
            user_id,
            requested_action,
            _dump_json(_redact_sensitive(input_manifest)),
            idempotency_key,
            trace_id,
            code_version,
            container_image_digest,
            dependency_lock_hash,
            environment_class,
            _dump_json(feature_flags or {}),
            SOURCE_POLICY_VERSION,
            now,
            now,
        ),
    )
    _append_event(
        conn,
        run_id,
        event_type="run_created",
        status="queued",
        stage="queued",
        message="Run queued for cloud execution.",
        payload={"requested_action": requested_action},
        trace_id=trace_id,
        created_at=now,
    )
    conn.commit()
    return get_run(conn, run_id)


def find_run_by_idempotency_key(
    conn: StoreConnection, user_id: str, idempotency_key: str | None
) -> dict[str, object] | None:
    if not idempotency_key:
        return None
    row = conn.execute(
        """
        SELECT *
        FROM cloud_runs
        WHERE user_id = ?
          AND idempotency_key = ?
        """,
        (user_id, idempotency_key),
    ).fetchone()
    return _run_from_row(row) if row is not None else None


def get_run(conn: StoreConnection, run_id: str) -> dict[str, object]:
    row = conn.execute("SELECT * FROM cloud_runs WHERE id = ?", (run_id,)).fetchone()
    if row is None:
        raise RunNotFound(run_id)
    return _run_from_row(row)


def list_run_events(conn: StoreConnection, run_id: str) -> list[dict[str, object]]:
    get_run(conn, run_id)
    rows = conn.execute(
        """
        SELECT *
        FROM cloud_run_events
        WHERE run_id = ?
        ORDER BY id ASC
        """,
        (run_id,),
    ).fetchall()
    return [_event_from_row(row) for row in rows]


def list_runs(conn: StoreConnection, *, user_id: str | None = None) -> list[dict[str, object]]:
    if user_id is None:
        rows = conn.execute(
            f"""
            SELECT *
            FROM cloud_runs
            ORDER BY {CLOUD_RUN_QUEUE_ORDER}
            """
        ).fetchall()
    else:
        rows = conn.execute(
            f"""
            SELECT *
            FROM cloud_runs
            WHERE user_id = ?
            ORDER BY {CLOUD_RUN_QUEUE_ORDER}
            """,
            (user_id,),
        ).fetchall()
    return [_run_from_row(row) for row in rows]


def get_run_for_user(
    conn: StoreConnection, run_id: str, *, user_id: str
) -> dict[str, object]:
    run = get_run(conn, run_id)
    if str(run["user_id"]) != user_id:
        raise RunNotFound(run_id)
    return run


def record_run_stage_result(
    conn: StoreConnection,
    run_id: str,
    *,
    stage: str,
    result: dict[str, object],
    event_type: str | None = None,
    message: str | None = None,
) -> dict[str, object]:
    run = get_run(conn, run_id)
    output_manifest = dict(run["output_manifest"])
    output_manifest[stage] = result
    _set_run_state(
        conn,
        run_id,
        status="running",
        stage=stage,
        output_manifest=output_manifest,
    )
    _append_event(
        conn,
        run_id,
        event_type=event_type or f"{stage}_completed",
        status="running",
        stage=stage,
        message=message or f"Cloud run stage completed: {stage}.",
        payload=result,
        trace_id=str(run["trace_id"]),
    )
    conn.commit()
    return get_run(conn, run_id)


def complete_run(
    conn: StoreConnection,
    run_id: str,
    *,
    result: dict[str, object] | None = None,
) -> dict[str, object]:
    run = get_run(conn, run_id)
    output_manifest = dict(run["output_manifest"])
    if result is not None:
        output_manifest["completion"] = result
    _set_run_state(
        conn,
        run_id,
        status="completed",
        stage="completed",
        output_manifest=output_manifest,
        completed_at=_now(),
    )
    _append_event(
        conn,
        run_id,
        event_type="run_completed",
        status="completed",
        stage="completed",
        message="Cloud run completed.",
        payload=result or {},
        trace_id=str(run["trace_id"]),
    )
    conn.commit()
    return get_run(conn, run_id)


def fail_run(
    conn: StoreConnection,
    run_id: str,
    *,
    error_code: str,
    error_message: str,
) -> dict[str, object]:
    run = get_run(conn, run_id)
    _set_run_state(
        conn,
        run_id,
        status="failed",
        stage="failed",
        completed_at=_now(),
        error_code=error_code,
        error_message=error_message,
    )
    _append_event(
        conn,
        run_id,
        event_type="run_failed",
        status="failed",
        stage="failed",
        message=error_message,
        payload={"error_code": error_code, "error_message": error_message},
        trace_id=str(run["trace_id"]),
    )
    conn.commit()
    return get_run(conn, run_id)


def build_runtime_readiness_report(conn: StoreConnection) -> dict[str, object]:
    runs = list_runs(conn)
    run_counts = {status: 0 for status in sorted(RUN_STATUSES)}
    for run in runs:
        run_counts[str(run["status"])] = run_counts.get(str(run["status"]), 0) + 1
    active_runs = [
        run
        for run in runs
        if run["status"] not in TERMINAL_STATUSES and run["status"] != "completed"
    ]
    terminal_runs = [run for run in runs if run["status"] in TERMINAL_STATUSES]
    user_action_runs = [run for run in runs if run["status"] == "waiting_for_user"]
    return {
        "status": "ok",
        "service": "ml-job-swarm",
        "database": "ok",
        "slo_targets": dict(SLO_TARGETS),
        "run_counts": run_counts,
        "active_run_ids": [str(run["id"]) for run in active_runs],
        "terminal_run_ids": [str(run["id"]) for run in terminal_runs],
        "runs_requiring_user_action": [str(run["id"]) for run in user_action_runs],
        "total_runs": len(runs),
    }


def compare_runtime_parity(
    *,
    local: list[dict[str, object]],
    cloud: list[dict[str, object]],
    p0_threshold: float = 0.99,
) -> dict[str, object]:
    local_by_id = {str(item["id"]): item for item in local}
    cloud_by_id = {str(item["id"]): item for item in cloud}
    all_ids = sorted(set(local_by_id) | set(cloud_by_id))
    matches = 0
    mismatches = []
    for item_id in all_ids:
        local_decision = local_by_id.get(item_id, {}).get("decision")
        cloud_decision = cloud_by_id.get(item_id, {}).get("decision")
        if local_decision == cloud_decision:
            matches += 1
        else:
            mismatches.append(
                {
                    "id": item_id,
                    "local_decision": local_decision,
                    "cloud_decision": cloud_decision,
                }
            )
    match_rate = 1.0 if not all_ids else matches / len(all_ids)
    return {
        "match_rate": match_rate,
        "matches": matches,
        "total": len(all_ids),
        "meets_p0": match_rate >= p0_threshold,
        "mismatches": mismatches,
    }


def evaluate_source_for_run(
    conn: StoreConnection, run_id: str, url: str
) -> dict[str, object]:
    run = get_run(conn, run_id)
    policy = classify_source_url(url)
    payload = {
        "url": url,
        "normalized_url": policy.normalized_url,
        "mode": policy.mode,
        "reason": policy.reason,
        "network_scheduled": False,
    }
    if policy.mode == "allowed":
        _append_event(
            conn,
            run_id,
            event_type="source_policy_allowed",
            status=run["status"],
            stage="source_policy",
            message="Source allowed by policy.",
            payload=payload,
            trace_id=str(run["trace_id"]),
        )
        conn.commit()
        return {
            **_policy_payload(policy),
            "network_scheduled": False,
            "next_action": None,
        }

    next_action = (
        "provide_allowed_employer_or_ats_source"
        if policy.mode == "blocked"
        else "review_source_manually"
    )
    status = "waiting_for_user"
    _set_run_state(
        conn,
        run_id,
        status=status,
        stage="source_policy",
        next_action=next_action,
    )
    _append_event(
        conn,
        run_id,
        event_type=(
            "source_policy_denied"
            if policy.mode == "blocked"
            else "source_policy_manual_review_required"
        ),
        status=status,
        stage="source_policy",
        message="Source requires user action before cloud execution.",
        payload=payload,
        trace_id=str(run["trace_id"]),
    )
    conn.commit()
    return {
        **_policy_payload(policy),
        "network_scheduled": False,
        "next_action": next_action,
    }


def record_prepared_packet(
    conn: StoreConnection, run_id: str, packet_manifest: dict[str, object]
) -> dict[str, object]:
    missing = sorted(REQUIRED_PACKET_MANIFEST_FIELDS - packet_manifest.keys())
    if missing:
        raise ValueError(f"prepared packet manifest missing {', '.join(missing)}")

    run = get_run(conn, run_id)
    output_manifest = dict(run["output_manifest"])
    packets = list(output_manifest.get("prepared_packets", []))
    packets.append(_redact_sensitive(packet_manifest))
    output_manifest["prepared_packets"] = packets
    _set_run_state(
        conn,
        run_id,
        status="prepared",
        stage="application_packet",
        output_manifest=output_manifest,
        next_action="manual_final_submit",
    )
    _append_event(
        conn,
        run_id,
        event_type="packet_prepared",
        status="prepared",
        stage="application_packet",
        message="Application packet prepared for user review.",
        payload=packet_manifest,
        trace_id=str(run["trace_id"]),
    )
    conn.commit()
    return get_run(conn, run_id)


def create_manual_final_submit_instruction(
    conn: StoreConnection,
    run_id: str,
    *,
    packet_id: str | None = None,
    apply_url: str | None = None,
    requested_by_automation: bool = False,
) -> dict[str, object]:
    instruction = {
        "manual_final_submit_required": True,
        "automation_allowed": False,
        "packet_id": packet_id,
        "apply_url": apply_url,
        "next_action": "manual_final_submit",
        "message": "Review the prepared packet and complete the final submit manually.",
    }
    if requested_by_automation:
        raise ManualFinalSubmitBlocked(instruction)

    run = get_run(conn, run_id)
    _set_run_state(
        conn,
        run_id,
        status="waiting_for_user",
        stage="manual_final_submit",
        next_action="manual_final_submit",
    )
    _append_event(
        conn,
        run_id,
        event_type="manual_final_submit_required",
        status="waiting_for_user",
        stage="manual_final_submit",
        message="Cloud runtime stopped at manual final submit boundary.",
        payload=instruction,
        trace_id=str(run["trace_id"]),
    )
    conn.commit()
    return instruction


def record_run_heartbeat(
    conn: StoreConnection, run_id: str, *, stage: str | None = None
) -> dict[str, object]:
    run = get_run(conn, run_id)
    heartbeat_stage = stage or str(run["current_stage"])
    now = _now()
    _set_run_state(
        conn,
        run_id,
        status="running",
        stage=heartbeat_stage,
        last_heartbeat_at=now,
        started_at=str(run["started_at"] or now),
    )
    _append_event(
        conn,
        run_id,
        event_type="heartbeat",
        status="running",
        stage=heartbeat_stage,
        message="Cloud run heartbeat.",
        payload={"heartbeat_at": now},
        trace_id=str(run["trace_id"]),
        created_at=now,
    )
    conn.commit()
    return get_run(conn, run_id)


def cancel_run(
    conn: StoreConnection, run_id: str, *, reason: str | None = None
) -> dict[str, object]:
    run = get_run(conn, run_id)
    now = _now()
    _set_run_state(
        conn,
        run_id,
        status="canceled",
        stage="canceled",
        completed_at=now,
        cancel_requested_at=now,
    )
    _append_event(
        conn,
        run_id,
        event_type="run_canceled",
        status="canceled",
        stage="canceled",
        message=reason or "Run canceled.",
        payload={"reason": reason},
        trace_id=str(run["trace_id"]),
        created_at=now,
    )
    conn.commit()
    return get_run(conn, run_id)


def _set_run_state(
    conn: StoreConnection,
    run_id: str,
    *,
    status: str,
    stage: str,
    output_manifest: dict[str, object] | None = None,
    next_action: str | None = None,
    last_heartbeat_at: str | None = None,
    started_at: str | None = None,
    completed_at: str | None = None,
    cancel_requested_at: str | None = None,
    error_code: str | None = None,
    error_message: str | None = None,
) -> None:
    if status not in RUN_STATUSES:
        raise InvalidRunTransition(f"unknown run status: {status}")
    current = get_run(conn, run_id)
    if current["status"] in TERMINAL_STATUSES and current["status"] != status:
        raise InvalidRunTransition("terminal cloud runs cannot transition")
    conn.execute(
        """
        UPDATE cloud_runs
        SET status = ?,
            current_stage = ?,
            output_manifest_json = COALESCE(?, output_manifest_json),
            next_action = ?,
            last_heartbeat_at = COALESCE(?, last_heartbeat_at),
            started_at = COALESCE(?, started_at),
            completed_at = COALESCE(?, completed_at),
            cancel_requested_at = COALESCE(?, cancel_requested_at),
            error_code = COALESCE(?, error_code),
            error_message = COALESCE(?, error_message),
            updated_at = ?
        WHERE id = ?
        """,
        (
            status,
            stage,
            _dump_json(_redact_sensitive(output_manifest))
            if output_manifest is not None
            else None,
            next_action,
            last_heartbeat_at,
            started_at,
            completed_at,
            cancel_requested_at,
            error_code,
            error_message,
            _now(),
            run_id,
        ),
    )


def _append_event(
    conn: StoreConnection,
    run_id: str,
    *,
    event_type: str,
    status: str,
    stage: str,
    message: str,
    payload: dict[str, object] | None,
    trace_id: str,
    created_at: str | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO cloud_run_events (
          run_id,
          event_type,
          status,
          stage,
          message,
          payload_json,
          trace_id,
          created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id,
            event_type,
            status,
            stage,
            message,
            _dump_json(_redact_sensitive(payload or {})),
            trace_id,
            created_at or _now(),
        ),
    )


def _run_from_row(row: Mapping[str, Any]) -> dict[str, object]:
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "requested_action": row["requested_action"],
        "status": row["status"],
        "current_stage": row["current_stage"],
        "input_manifest": _load_json(row["input_manifest_json"]),
        "output_manifest": _load_json(row["output_manifest_json"]),
        "idempotency_key": row["idempotency_key"],
        "trace_id": row["trace_id"],
        "code_version": row["code_version"],
        "container_image_digest": row["container_image_digest"],
        "dependency_lock_hash": row["dependency_lock_hash"],
        "environment_class": row["environment_class"],
        "feature_flags": _load_json(row["feature_flags_json"]),
        "source_policy_version": row["source_policy_version"],
        "next_action": row["next_action"],
        "error_code": row["error_code"],
        "error_message": row["error_message"],
        "created_at": _serialize_db_value(row["created_at"]),
        "updated_at": _serialize_db_value(row["updated_at"]),
        "started_at": _serialize_db_value(row["started_at"]),
        "completed_at": _serialize_db_value(row["completed_at"]),
        "last_heartbeat_at": _serialize_db_value(row["last_heartbeat_at"]),
        "cancel_requested_at": _serialize_db_value(row["cancel_requested_at"]),
    }


def _event_from_row(row: Mapping[str, Any]) -> dict[str, object]:
    return {
        "id": row["id"],
        "run_id": row["run_id"],
        "event_type": row["event_type"],
        "status": row["status"],
        "stage": row["stage"],
        "message": row["message"],
        "payload": _load_json(row["payload_json"]),
        "trace_id": row["trace_id"],
        "created_at": _serialize_db_value(row["created_at"]),
    }


def _serialize_db_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat()
    return value


def _policy_payload(policy: SourcePolicyResult) -> dict[str, object]:
    return {
        "mode": policy.mode,
        "reason": policy.reason,
        "normalized_url": policy.normalized_url,
    }


def _dump_json(value: dict[str, object] | list[object]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _redact_sensitive(value: object, *, key_name: str | None = None) -> object:
    if key_name is not None and _is_sensitive_key(key_name):
        return "[redacted]"
    if isinstance(value, dict):
        return {
            str(key): _redact_sensitive(item, key_name=str(key))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact_sensitive(item) for item in value]
    return value


def _is_sensitive_key(key: str) -> bool:
    normalized = key.lower()
    return any(term in normalized for term in SENSITIVE_KEY_TERMS)


def _load_json(value: str | None) -> object:
    if not value:
        return {}
    return json.loads(value)


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")
