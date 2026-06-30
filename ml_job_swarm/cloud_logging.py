from __future__ import annotations

ALLOWED_STATUSES = {
    "queued",
    "running",
    "waiting_for_user",
    "prepared",
    "failed",
    "canceled",
    "completed",
}

REQUIRED_TRANSITION_LOG_FIELDS = (
    "run_id",
    "stage",
    "trace_id",
    "duration_ms",
    "event_type",
    "status",
)


def build_transition_log(
    *,
    run_id: str,
    stage: str,
    trace_id: str,
    duration_ms: int,
    event_type: str,
    status: str,
) -> dict[str, object]:
    return {
        "run_id": run_id,
        "stage": stage,
        "trace_id": trace_id,
        "duration_ms": duration_ms,
        "event_type": event_type,
        "status": status,
    }


def validate_transition_log(log: dict[str, object]) -> list[str]:
    violations: list[str] = []
    for field in REQUIRED_TRANSITION_LOG_FIELDS:
        if field not in log:
            violations.append(f"missing required field: {field}")

    run_id = log.get("run_id")
    if "run_id" in log and (not isinstance(run_id, str) or not run_id):
        violations.append("run_id must be a non-empty string")

    stage = log.get("stage")
    if "stage" in log and (not isinstance(stage, str) or not stage):
        violations.append("stage must be a non-empty string")

    trace_id = log.get("trace_id")
    if "trace_id" in log and (not isinstance(trace_id, str) or not trace_id):
        violations.append("trace_id must be a non-empty string")

    duration_ms = log.get("duration_ms")
    if "duration_ms" in log and not isinstance(duration_ms, int):
        violations.append("duration_ms must be an integer")
    elif isinstance(duration_ms, int) and duration_ms < 0:
        violations.append("duration_ms must be non-negative")

    event_type = log.get("event_type")
    if "event_type" in log and (not isinstance(event_type, str) or not event_type):
        violations.append("event_type must be a non-empty string")

    status = log.get("status")
    if "status" in log and (not isinstance(status, str) or not status):
        violations.append("status must be a non-empty string")
    elif isinstance(status, str) and status and status not in ALLOWED_STATUSES:
        violations.append(f"status must be one of {sorted(ALLOWED_STATUSES)}")

    return violations
