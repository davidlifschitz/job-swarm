from __future__ import annotations

import argparse
import json
import os
from collections.abc import Callable

from ml_job_swarm.adapters import public_ats_registry
from ml_job_swarm.cloud_runtime import StoreConnection
from ml_job_swarm.cloud_runtime import (
    RunNotFound,
    complete_run,
    create_manual_final_submit_instruction,
    evaluate_source_for_run,
    fail_run,
    get_run,
    record_prepared_packet,
    record_run_heartbeat,
    record_run_stage_result,
)
from ml_job_swarm.filtering import (
    review_jobs_for_profile_resilient,
    rules_preview_jobs,
)
from ml_job_swarm.ingest import AdapterRegistry, refresh_due_sources, refresh_source
from ml_job_swarm.db.dialect import BackendKind
from ml_job_swarm.db.factory import backend_kind_from_env, connect_from_env
from ml_job_swarm.store import connect, init_db

PacketPreparer = Callable[[StoreConnection, int, int], int]


def run_cloud_workflow_once(
    conn: StoreConnection,
    *,
    adapter_registry: AdapterRegistry,
    fit_gate_client: object | None = None,
    run_id: str | None = None,
    packet_preparer: PacketPreparer | None = None,
) -> dict[str, object]:
    run = get_run(conn, run_id) if run_id is not None else _next_queued_run(conn)
    if run is None:
        return {"status": "idle", "run_id": None}
    if run["status"] != "queued":
        return _worker_result(run)

    run_id = str(run["id"])
    try:
        record_run_heartbeat(conn, run_id, stage="starting")
        manifest = dict(run["input_manifest"])

        blocked = _evaluate_manifest_sources(conn, run_id, manifest)
        if blocked is not None:
            return blocked

        refresh_result = _refresh_sources(conn, run_id, manifest, adapter_registry)
        if refresh_result is not None and refresh_result["status"] == "waiting_for_user":
            return refresh_result

        target_profile_id = _optional_int(manifest.get("target_profile_id"))
        if target_profile_id is not None:
            _match_jobs(
                conn,
                run_id,
                target_profile_id=target_profile_id,
                fit_gate_client=fit_gate_client,
                review_with_llm=bool(manifest.get("review_jobs_with_llm")),
            )

        if target_profile_id is not None and bool(manifest.get("prepare_packets")):
            prepared = _prepare_packets(
                conn,
                run_id,
                target_profile_id=target_profile_id,
                manifest=manifest,
                packet_preparer=packet_preparer or _default_packet_preparer,
            )
            if prepared:
                instruction = create_manual_final_submit_instruction(
                    conn,
                    run_id,
                    packet_id=str(prepared[0]["packet_id"]),
                    apply_url=str(prepared[0].get("apply_url") or ""),
                )
                return _worker_result(get_run(conn, run_id), instruction)

        return _worker_result(
            complete_run(
                conn,
                run_id,
                result={"message": "Cloud workflow completed without manual submit."},
            )
        )
    except Exception as exc:
        from ml_job_swarm.error_sanitize import sanitize_error_message

        failed = fail_run(
            conn,
            run_id,
            error_code="cloud_worker_failed",
            error_message=sanitize_error_message(exc),
        )
        return _worker_result(failed)


def run_cloud_worker_loop(
    conn: StoreConnection,
    *,
    adapter_registry: AdapterRegistry,
    fit_gate_client: object | None = None,
    max_runs: int | None = None,
    packet_preparer: PacketPreparer | None = None,
) -> dict[str, object]:
    processed = []
    unlimited = max_runs is None or max_runs <= 0
    while unlimited or len(processed) < max_runs:
        result = run_cloud_workflow_once(
            conn,
            adapter_registry=adapter_registry,
            fit_gate_client=fit_gate_client,
            packet_preparer=packet_preparer,
        )
        if result["status"] == "idle":
            return {
                "status": "idle",
                "idle": True,
                "runs_processed": len(processed),
                "results": processed,
            }
        processed.append(result)
    return {
        "status": "max_runs_reached",
        "idle": _next_queued_run(conn) is None,
        "runs_processed": len(processed),
        "results": processed,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the ml-job-swarm cloud worker.")
    parser.add_argument(
        "--db-path",
        default=os.environ.get("ML_JOB_SWARM_DB_PATH", "jobs.db"),
        help="SQLite database path. Defaults to ML_JOB_SWARM_DB_PATH or jobs.db.",
    )
    parser.add_argument(
        "--max-runs",
        type=int,
        default=1,
        help="Maximum queued runs to process before exiting.",
    )
    args = parser.parse_args(argv)

    conn = open_worker_connection(db_path=args.db_path)
    init_db(conn)
    summary = run_cloud_worker_loop(
        conn,
        adapter_registry=public_ats_registry(),
        max_runs=args.max_runs,
    )
    print(json.dumps(summary, sort_keys=True))
    return 0


def open_worker_connection(*, db_path: str) -> StoreConnection:
    if backend_kind_from_env() == BackendKind.POSTGRES:
        return connect_from_env()
    return connect(db_path)


def _next_queued_run(conn: StoreConnection) -> dict[str, object] | None:
    from ml_job_swarm.cloud_runtime import CLOUD_RUN_QUEUE_ORDER

    row = conn.execute(
        f"""
        SELECT id
        FROM cloud_runs
        WHERE status = 'queued'
        ORDER BY {CLOUD_RUN_QUEUE_ORDER}
        LIMIT 1
        """
    ).fetchone()
    if row is None:
        return None
    return get_run(conn, str(row["id"]))


def _evaluate_manifest_sources(
    conn: StoreConnection, run_id: str, manifest: dict[str, object]
) -> dict[str, object] | None:
    for url in _strings(manifest.get("sources")):
        result = evaluate_source_for_run(conn, run_id, url)
        if result["mode"] != "allowed":
            return _worker_result(get_run(conn, run_id), result)
    return None


def _refresh_sources(
    conn: StoreConnection,
    run_id: str,
    manifest: dict[str, object],
    adapter_registry: AdapterRegistry,
) -> dict[str, object] | None:
    source_ids = _ints(manifest.get("source_ids"))
    if not source_ids and not bool(manifest.get("refresh_due_sources")):
        return None

    record_run_heartbeat(conn, run_id, stage="refresh_sources")
    if source_ids:
        aggregate = {
            "sources_seen": len(source_ids),
            "sources_attempted": 0,
            "sources_succeeded": 0,
            "sources_refreshed": 0,
            "jobs_seen": 0,
            "jobs_closed": 0,
            "failures": 0,
            "blocked": 0,
            "suspicious_empty": 0,
        }
        for source_id in source_ids:
            source = _source_row(conn, source_id)
            policy = evaluate_source_for_run(conn, run_id, str(source["url"]))
            if policy["mode"] != "allowed":
                aggregate["blocked"] += 1
                record_run_stage_result(
                    conn,
                    run_id,
                    stage="refresh",
                    result=aggregate,
                    event_type="refresh_blocked",
                )
                return _worker_result(get_run(conn, run_id), policy)
            adapter = adapter_registry.adapter_for(str(source["source_type"]))
            refresh = refresh_source(conn, source_id, adapter)
            aggregate["sources_attempted"] += 1
            aggregate["jobs_seen"] += refresh.jobs_seen
            aggregate["jobs_closed"] += refresh.jobs_closed
            if refresh.status == "ok":
                aggregate["sources_succeeded"] += 1
                aggregate["sources_refreshed"] += 1
            else:
                aggregate["failures"] += 1
        record_run_stage_result(
            conn,
            run_id,
            stage="refresh",
            result=aggregate,
            event_type="refresh_completed",
        )
        return None

    summary = refresh_due_sources(conn, adapter_registry)
    record_run_stage_result(
        conn,
        run_id,
        stage="refresh",
        result={
            "sources_seen": summary.sources_seen,
            "sources_attempted": summary.sources_attempted,
            "sources_succeeded": summary.sources_succeeded,
            "sources_refreshed": summary.sources_refreshed,
            "jobs_seen": summary.jobs_seen,
            "jobs_closed": summary.jobs_closed,
            "failures": summary.failures,
            "blocked": summary.blocked,
            "suspicious_empty": summary.suspicious_empty,
        },
        event_type="refresh_completed",
    )
    return None


def _match_jobs(
    conn: StoreConnection,
    run_id: str,
    *,
    target_profile_id: int,
    fit_gate_client: object | None,
    review_with_llm: bool,
) -> None:
    record_run_heartbeat(conn, run_id, stage="matching")
    if review_with_llm and fit_gate_client is not None:
        batch = review_jobs_for_profile_resilient(
            conn, target_profile_id, fit_gate_client  # type: ignore[arg-type]
        )
        result = {
            "mode": "llm_fit_review",
            "reviews_created": len(batch.review_ids),
            "failures": len(batch.failures),
        }
    else:
        previews = rules_preview_jobs(conn, target_profile_id, limit=50)
        result = {
            "mode": "rules_preview",
            "rules_preview_count": len(previews),
            "candidate_job_ids": [preview.job_id for preview in previews],
        }
    record_run_stage_result(
        conn,
        run_id,
        stage="matching",
        result=result,
        event_type="matching_completed",
    )


def _prepare_packets(
    conn: StoreConnection,
    run_id: str,
    *,
    target_profile_id: int,
    manifest: dict[str, object],
    packet_preparer: PacketPreparer,
) -> list[dict[str, object]]:
    record_run_heartbeat(conn, run_id, stage="application_packet")
    max_packets = _optional_int(manifest.get("max_packets")) or 1
    job_ids = _ints(manifest.get("job_ids")) or _candidate_packet_job_ids(
        conn, target_profile_id, limit=max_packets
    )
    prepared = []
    for job_id in job_ids[:max_packets]:
        packet_id = packet_preparer(conn, job_id, target_profile_id)
        packet_manifest = _packet_manifest(conn, packet_id)
        record_prepared_packet(conn, run_id, packet_manifest)
        prepared.append(packet_manifest)
    return prepared


def _candidate_packet_job_ids(
    conn: StoreConnection, target_profile_id: int, *, limit: int
) -> list[int]:
    rows = conn.execute(
        """
        SELECT jobs.id
        FROM jobs
        LEFT JOIN rules_filter_results
          ON rules_filter_results.id = (
            SELECT MAX(id)
            FROM rules_filter_results
            WHERE job_id = jobs.id
              AND target_profile_id = ?
          )
        LEFT JOIN job_decisions
          ON job_decisions.job_id = jobs.id
         AND job_decisions.target_profile_id = ?
        WHERE jobs.status = 'open'
          AND COALESCE(job_decisions.decision, 'saved') != 'hidden'
        ORDER BY COALESCE(rules_filter_results.score, 0) DESC, jobs.id ASC
        LIMIT ?
        """,
        (target_profile_id, target_profile_id, limit),
    ).fetchall()
    return [int(row["id"]) for row in rows]


def _packet_manifest(conn: StoreConnection, packet_id: int) -> dict[str, object]:
    row = conn.execute(
        """
        SELECT
          application_packets.id,
          application_packets.job_id,
          application_packets.target_profile_id,
          application_packets.manual_submit_url,
          jobs.source_url,
          jobs.apply_url,
          resume_assets.storage_path AS resume_pdf_path,
          resume_assets.sha256 AS resume_sha256,
          (
            SELECT MAX(id)
            FROM fit_reviews
            WHERE fit_reviews.job_id = application_packets.job_id
              AND fit_reviews.target_profile_id = application_packets.target_profile_id
          ) AS fit_review_id,
          (
            SELECT MAX(id)
            FROM rules_filter_results
            WHERE rules_filter_results.job_id = application_packets.job_id
              AND rules_filter_results.target_profile_id = application_packets.target_profile_id
          ) AS rules_result_id
        FROM application_packets
        JOIN jobs ON jobs.id = application_packets.job_id
        JOIN target_profiles ON target_profiles.id = application_packets.target_profile_id
        LEFT JOIN resume_assets ON resume_assets.id = target_profiles.resume_asset_id
        WHERE application_packets.id = ?
        """,
        (packet_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"Application packet not found: {packet_id}")
    decision_id = (
        f"fit_review:{row['fit_review_id']}"
        if row["fit_review_id"] is not None
        else f"rules_filter:{row['rules_result_id']}"
        if row["rules_result_id"] is not None
        else f"job:{row['job_id']}"
    )
    apply_url = row["manual_submit_url"] or row["apply_url"] or ""
    return {
        "packet_id": str(row["id"]),
        "job_id": int(row["job_id"]),
        "target_profile_id": int(row["target_profile_id"]),
        "resume_pdf_path": row["resume_pdf_path"] or "",
        "source_url": row["source_url"] or "",
        "apply_url": apply_url,
        "decision_id": decision_id,
        "artifact_checksums": {
            "application_packet": f"application_packet:{row['id']}",
            "resume": row["resume_sha256"] or "",
        },
        "review_status": "prepared",
    }


def _source_row(conn: StoreConnection, source_id: int):
    row = conn.execute(
        """
        SELECT id, url, source_type
        FROM job_sources
        WHERE id = ?
        """,
        (source_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"Job source not found: {source_id}")
    return row


def _default_packet_preparer(
    conn: StoreConnection, job_id: int, target_profile_id: int
) -> int:
    from ml_job_swarm.app import _prepare_application_packet

    return _prepare_application_packet(
        conn, job_id=job_id, target_profile_id=target_profile_id
    )


def _worker_result(
    run: dict[str, object], extra: dict[str, object] | None = None
) -> dict[str, object]:
    return {"run_id": run["id"], **run, **(extra or {})}


def _ints(value: object) -> list[int]:
    if value is None:
        return []
    if isinstance(value, int):
        return [value]
    if isinstance(value, list):
        return [int(item) for item in value]
    return [int(value)]


def _strings(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]


def _optional_int(value: object) -> int | None:
    if value in (None, ""):
        return None
    return int(value)


if __name__ == "__main__":
    raise SystemExit(main())
