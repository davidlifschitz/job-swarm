from __future__ import annotations

import sqlite3
from pathlib import Path

CATALOG_TABLES = (
    "companies",
    "job_sources",
    "company_source_review_queue",
    "jobs",
    "ingestion_runs",
    "source_friction_events",
    "job_snapshots",
)


def import_job_catalog(
    conn: sqlite3.Connection,
    source_path: Path,
    *,
    skip_if_jobs_exist: bool = True,
) -> dict[str, object]:
    from ml_job_swarm.db.postgres_backend import PostgresDatabase

    if isinstance(conn, PostgresDatabase):
        return {
            "status": "skipped",
            "reason": "postgres_unsupported",
            "path": str(source_path),
        }

    if not source_path.exists():
        return {"status": "skipped", "reason": "source_missing", "path": str(source_path)}

    source_jobs = _table_count(source_path, "jobs")
    if source_jobs == 0:
        return {"status": "skipped", "reason": "source_empty", "path": str(source_path)}

    if skip_if_jobs_exist:
        existing_jobs = conn.execute("SELECT COUNT(*) AS count FROM jobs").fetchone()
        if existing_jobs and int(existing_jobs["count"]) > 0:
            return {"status": "skipped", "reason": "destination_has_jobs"}

    imported: dict[str, int] = {}
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute("ATTACH DATABASE ? AS legacy", (str(source_path),))
    try:
        for table in CATALOG_TABLES:
            if not _legacy_table_exists(conn, table):
                imported[table] = 0
                continue
            before = conn.execute(f"SELECT COUNT(*) AS count FROM {table}").fetchone()
            conn.execute(
                f"""
                INSERT OR IGNORE INTO main.{table}
                SELECT * FROM legacy.{table}
                """
            )
            after = conn.execute(f"SELECT COUNT(*) AS count FROM {table}").fetchone()
            imported[table] = int(after["count"]) - int(before["count"])
        conn.commit()
    finally:
        conn.execute("DETACH DATABASE legacy")
        conn.execute("PRAGMA foreign_keys = ON")

    return {
        "status": "ok",
        "path": str(source_path),
        "source_jobs": source_jobs,
        "imported": imported,
    }


def _table_count(path: Path, table: str) -> int:
    legacy = sqlite3.connect(path)
    legacy.row_factory = sqlite3.Row
    try:
        row = legacy.execute(f"SELECT COUNT(*) AS count FROM {table}").fetchone()
        return int(row["count"]) if row else 0
    except sqlite3.OperationalError:
        return 0
    finally:
        legacy.close()


def _legacy_table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        """
        SELECT 1
        FROM legacy.sqlite_master
        WHERE type = 'table' AND name = ?
        """,
        (table,),
    ).fetchone()
    return row is not None