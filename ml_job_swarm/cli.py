from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from ml_job_swarm.adapters import public_ats_registry
from ml_job_swarm.catalog import import_seed_companies
from ml_job_swarm.ingest import AdapterRegistry, JobSource, RawJob, refresh_due_sources
from ml_job_swarm.store import connect, init_db


class FixtureAdapter:
    def __init__(self, jobs: list[RawJob]):
        self._jobs = jobs

    def fetch_jobs(self, source: JobSource) -> list[RawJob]:
        return self._jobs


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ml-job-swarm")
    subparsers = parser.add_subparsers(dest="command", required=True)

    refresh = subparsers.add_parser(
        "refresh", help="Run a cron-friendly local catalog refresh"
    )
    refresh.add_argument("--db", required=True, help="SQLite database path")
    refresh.add_argument("--seed", help="Seed company JSON path")
    adapter_mode = refresh.add_mutually_exclusive_group(required=True)
    adapter_mode.add_argument(
        "--public-ats",
        action="store_true",
        help="Use built-in public ATS adapters for reviewed sources",
    )
    adapter_mode.add_argument(
        "--fixture-dir",
        help="Directory containing <source_type>_jobs.json fixture adapters",
    )

    args = parser.parse_args(argv)
    if args.command == "refresh":
        return _refresh(args)
    parser.error(f"Unknown command: {args.command}")
    return 2


def _refresh(args: argparse.Namespace) -> int:
    conn = connect(Path(args.db))
    init_db(conn)

    imported = 0
    if args.seed:
        imported = import_seed_companies(conn, Path(args.seed))

    registry = (
        public_ats_registry()
        if args.public_ats
        else _fixture_registry(Path(args.fixture_dir))
    )
    skipped = _reviewed_source_count(conn) - _reviewed_source_count(
        conn, registry.source_types()
    )
    previous_run_id = _max_ingestion_run_id(conn)
    summary = refresh_due_sources(conn, registry, source_types=registry.source_types())
    friction_events, friction_status_codes = _friction_summary_since(
        conn, previous_run_id
    )
    payload = {
        "blocked": summary.blocked,
        "failures": summary.failures,
        "friction_events": friction_events,
        "friction_status_codes": friction_status_codes,
        "imported_companies": imported,
        "jobs_closed": summary.jobs_closed,
        "jobs_seen": summary.jobs_seen,
        "suspicious_empty": summary.suspicious_empty,
        "sources_attempted": summary.sources_attempted,
        "sources_refreshed": summary.sources_refreshed,
        "sources_seen": summary.sources_seen,
        "sources_succeeded": summary.sources_succeeded,
        "sources_skipped": skipped,
    }
    print(json.dumps(payload, sort_keys=True))
    return 1 if summary.failures else 0


def _fixture_registry(fixture_dir: Path) -> AdapterRegistry:
    adapters = {}
    for path in sorted(fixture_dir.glob("*_jobs.json")):
        source_type = path.name.removesuffix("_jobs.json")
        adapters[source_type] = FixtureAdapter(_load_jobs(path))
    return AdapterRegistry(adapters)


def _load_jobs(path: Path) -> list[RawJob]:
    payload = json.loads(path.read_text())
    if not isinstance(payload, list):
        raise ValueError(f"Fixture must be a JSON list: {path}")
    return [RawJob(**item) for item in payload]


def _reviewed_source_count(conn, source_types: set[str] | None = None) -> int:
    if source_types is None:
        row = conn.execute(
            """
            SELECT COUNT(*) FROM job_sources
            WHERE disabled_at IS NULL AND review_status = 'reviewed'
            """
        ).fetchone()
        return int(row[0])
    if not source_types:
        return 0
    placeholders = ", ".join("?" for _ in source_types)
    row = conn.execute(
        f"""
        SELECT COUNT(*) FROM job_sources
        WHERE disabled_at IS NULL
          AND review_status = 'reviewed'
          AND source_type IN ({placeholders})
        """,
        sorted(source_types),
    ).fetchone()
    return int(row[0])


def _max_ingestion_run_id(conn) -> int:
    row = conn.execute("SELECT COALESCE(MAX(id), 0) FROM ingestion_runs").fetchone()
    return int(row[0])


def _friction_summary_since(conn, run_id: int) -> tuple[dict[str, int], dict[str, int]]:
    event_counts = {
        str(row["event_type"]): int(row["count"])
        for row in conn.execute(
            """
            SELECT event_type, COUNT(*) AS count
            FROM source_friction_events
            WHERE ingestion_run_id > ?
            GROUP BY event_type
            ORDER BY event_type
            """,
            (run_id,),
        ).fetchall()
    }
    status_counts = {
        str(row["status_code"]): int(row["count"])
        for row in conn.execute(
            """
            SELECT status_code, COUNT(*) AS count
            FROM source_friction_events
            WHERE ingestion_run_id > ?
              AND status_code IS NOT NULL
            GROUP BY status_code
            ORDER BY status_code
            """,
            (run_id,),
        ).fetchall()
    }
    return event_counts, status_counts


if __name__ == "__main__":
    raise SystemExit(main())
