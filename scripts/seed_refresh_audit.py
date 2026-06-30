from __future__ import annotations

import argparse
import io
import json
import sys
import time
from contextlib import redirect_stdout
from pathlib import Path
from typing import Sequence

from ml_job_swarm.cli import main as cli_main
from ml_job_swarm.product_goals import build_live_smoke_product_metrics
from ml_job_swarm.store import connect, init_db

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures"
DEFAULT_SEED_PATH = REPO_ROOT / "data" / "seed_companies.json"

FIXTURE_SEED_SUBSET: list[dict[str, object]] = [
    {
        "name": "Example Greenhouse",
        "aliases": [],
        "tags": ["ai_infra"],
        "stage": "growth",
        "priority_tier": 1,
        "careers_url": "https://boards.greenhouse.io/example",
        "ats_type": "greenhouse",
        "reviewed_at": "2026-05-08",
    },
    {
        "name": "Example Lever",
        "aliases": [],
        "tags": ["ai_lab"],
        "stage": "growth",
        "priority_tier": 1,
        "careers_url": "https://jobs.lever.co/example",
        "ats_type": "lever",
        "reviewed_at": "2026-05-08",
    },
    {
        "name": "Example Custom",
        "aliases": [],
        "tags": ["developer_tools"],
        "stage": "growth",
        "priority_tier": 1,
        "careers_url": "https://example.com/careers",
        "ats_type": "custom",
        "reviewed_at": "2026-05-08",
    },
]


def write_fixture_seed_subset(seed_path: Path) -> Path:
    seed_path.write_text(json.dumps(FIXTURE_SEED_SUBSET), encoding="utf-8")
    return seed_path


def _max_ingestion_run_id(conn) -> int:
    row = conn.execute("SELECT COALESCE(MAX(id), 0) FROM ingestion_runs").fetchone()
    return int(row[0])


def load_source_failures(conn, *, since_run_id: int) -> list[dict[str, object]]:
    failures: list[dict[str, object]] = []
    rows = conn.execute(
        """
        SELECT event_type, url, status_code, details_json
        FROM source_friction_events
        WHERE ingestion_run_id > ?
        ORDER BY id
        """,
        (since_run_id,),
    ).fetchall()
    for row in rows:
        details = json.loads(row["details_json"] or "{}")
        failures.append(
            {
                "event_type": str(row["event_type"]),
                "url": str(row["url"]),
                "status_code": row["status_code"],
                "reason": _visible_failure_reason(row["event_type"], details),
            }
        )
    return failures


def _visible_failure_reason(event_type: object, details: dict[str, object]) -> str:
    for key in ("reason", "error", "event_type"):
        value = str(details.get(key) or "").strip()
        if value:
            return value
    return str(event_type or "").strip()


def evaluate_refresh_audit(
    *,
    refresh_summary: dict[str, object],
    product_metrics: dict[str, object],
) -> tuple[bool, list[str]]:
    violations: list[str] = []
    if int(refresh_summary.get("failures", 0) or 0) > 0:
        violations.append("refresh_failures")

    source_refresh = product_metrics["source_refresh"]
    if float(source_refresh["supported_source_success_rate"]) < float(
        source_refresh["target_success_rate"]
    ):
        violations.append("source_success_rate_below_target")

    if not bool(source_refresh["sources_have_visible_failure_reasons"]):
        violations.append("missing_visible_failure_reasons")

    catalog = product_metrics["catalog"]
    if int(catalog["jobs_seen"]) < int(catalog["target_jobs_seen_min"]):
        violations.append("jobs_seen_below_minimum")

    return not violations, violations


def _write_audit_artifact(payload: dict[str, object], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def evaluate_live_refresh_audit(
    db_path: Path,
    refresh_summary_path: Path,
    previous_run_id: int,
    output_path: Path | None = None,
) -> tuple[dict[str, object], int]:
    if not refresh_summary_path.is_file():
        print(
            "Missing refresh summary; live refresh did not produce JSON output.",
            file=sys.stderr,
        )
        return {}, 1

    refresh_summary = json.loads(
        refresh_summary_path.read_text(encoding="utf-8")
    )

    started_at = time.monotonic()
    conn = connect(db_path)
    source_failures = load_source_failures(conn, since_run_id=previous_run_id)
    conn.close()

    product_metrics = build_live_smoke_product_metrics(
        refresh_summary=refresh_summary,
        packet_prepared=False,
        saved_jobs_count=0,
        elapsed_seconds=round(time.monotonic() - started_at, 2),
        source_failures=source_failures,
    )
    audit_passed, audit_violations = evaluate_refresh_audit(
        refresh_summary=refresh_summary,
        product_metrics=product_metrics,
    )

    payload: dict[str, object] = {
        "audit_passed": audit_passed,
        "audit_violations": audit_violations,
        "product_metrics": product_metrics,
        "refresh_summary": refresh_summary,
        "source_failures": source_failures,
    }
    if output_path is not None:
        _write_audit_artifact(payload, output_path)

    exit_code = 0 if audit_passed else 1
    return payload, exit_code


def _emit_live_audit_diagnostics(payload: dict[str, object]) -> None:
    product_metrics = payload["product_metrics"]
    refresh_summary = payload["refresh_summary"]
    source_refresh = product_metrics["source_refresh"]
    success_rate = float(source_refresh["supported_source_success_rate"])
    target_success_rate = float(source_refresh["target_success_rate"])
    if success_rate < target_success_rate:
        print(
            f"Supported source success rate {success_rate:.4f} "
            f"is below target {target_success_rate:.4f}.",
            file=sys.stderr,
        )

    if int(refresh_summary.get("failures", 0) or 0) > 0:
        print(
            f"Refresh reported {refresh_summary['failures']} failure(s).",
            file=sys.stderr,
        )


def run_seed_refresh_audit(
    *,
    db_path: Path,
    seed_path: Path,
    fixture_dir: Path,
) -> tuple[dict[str, object], int]:
    started_at = time.monotonic()
    conn = connect(db_path)
    init_db(conn)
    previous_run_id = _max_ingestion_run_id(conn)
    conn.close()

    refresh_args = [
        "refresh",
        "--db",
        str(db_path),
        "--seed",
        str(seed_path),
        "--fixture-dir",
        str(fixture_dir),
    ]
    output = io.StringIO()
    with redirect_stdout(output):
        refresh_exit_code = cli_main(refresh_args)
    refresh_summary = json.loads(output.getvalue())

    conn = connect(db_path)
    source_failures = load_source_failures(conn, since_run_id=previous_run_id)
    conn.close()

    product_metrics = build_live_smoke_product_metrics(
        refresh_summary=refresh_summary,
        packet_prepared=False,
        saved_jobs_count=0,
        elapsed_seconds=round(time.monotonic() - started_at, 2),
        source_failures=source_failures,
    )
    audit_passed, audit_violations = evaluate_refresh_audit(
        refresh_summary=refresh_summary,
        product_metrics=product_metrics,
    )

    payload: dict[str, object] = {
        "audit_passed": audit_passed,
        "audit_violations": audit_violations,
        "product_metrics": product_metrics,
        "refresh_summary": refresh_summary,
        "source_failures": source_failures,
    }
    exit_code = 0 if audit_passed and refresh_exit_code == 0 else 1
    return payload, exit_code


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    output_path = Path(args.output) if args.output else None

    if args.evaluate_live:
        payload, exit_code = evaluate_live_refresh_audit(
            db_path=Path(args.db),
            refresh_summary_path=Path(args.refresh_summary),
            previous_run_id=args.previous_run_id,
            output_path=output_path,
        )
        if not payload:
            return exit_code
        _emit_live_audit_diagnostics(payload)
    else:
        payload, exit_code = run_seed_refresh_audit(
            db_path=Path(args.db),
            seed_path=Path(args.seed),
            fixture_dir=Path(args.fixture_dir),
        )
        if output_path is not None:
            _write_audit_artifact(payload, output_path)

    print(json.dumps(payload, sort_keys=True))
    return exit_code


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run a seed refresh audit offline with fixtures or evaluate a live "
            "refresh summary against audit metrics."
        )
    )
    parser.add_argument("--db", required=True, help="SQLite database path")
    parser.add_argument(
        "--output",
        help="Write the audit JSON artifact to this path",
    )
    parser.add_argument(
        "--evaluate-live",
        action="store_true",
        help="Evaluate a live refresh summary instead of running fixture refresh",
    )
    parser.add_argument(
        "--refresh-summary",
        help="Path to refresh summary JSON (required with --evaluate-live)",
    )
    parser.add_argument(
        "--previous-run-id",
        type=int,
        help="Latest ingestion run id before the live refresh (required with --evaluate-live)",
    )
    parser.add_argument(
        "--seed",
        default=str(DEFAULT_SEED_PATH),
        help="Seed company JSON path (offline fixture mode)",
    )
    parser.add_argument(
        "--fixture-dir",
        default=str(DEFAULT_FIXTURE_DIR),
        help="Directory containing <source_type>_jobs.json fixture adapters",
    )
    args = parser.parse_args(argv)
    if args.evaluate_live:
        missing: list[str] = []
        if not args.refresh_summary:
            missing.append("--refresh-summary")
        if args.previous_run_id is None:
            missing.append("--previous-run-id")
        if missing:
            parser.error(
                f"--evaluate-live requires {' and '.join(missing)}"
            )
    return args


if __name__ == "__main__":
    raise SystemExit(main())
