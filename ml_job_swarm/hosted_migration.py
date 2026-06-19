from __future__ import annotations

import hashlib
import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ml_job_swarm.db.factory import connect_from_env
from ml_job_swarm.db.postgres_backend import PostgresDatabase
from ml_job_swarm.db.postgres_schema import apply_postgres_schema, postgres_table_columns
from ml_job_swarm.resume_assets import RESUME_ASSET_URI_PREFIX
from ml_job_swarm.resume_storage import (
    SUPABASE_RESUME_URI_PREFIX,
    LocalResumeStorage,
    SupabaseResumeStorage,
    resume_storage_from_env,
)
from ml_job_swarm.store import connect, init_db, table_columns

MIGRATION_TABLE_ORDER: tuple[str, ...] = (
    "companies",
    "job_sources",
    "company_source_review_queue",
    "ingestion_runs",
    "llm_requests",
    "resume_assets",
    "resume_parse_runs",
    "resume_sections",
    "resume_keywords",
    "target_profiles",
    "preference_answers",
    "contacts",
    "jobs",
    "job_snapshots",
    "source_friction_events",
    "admin_audit_events",
    "rules_filter_results",
    "fit_reviews",
    "resume_rewrite_suggestions",
    "job_decisions",
    "application_packets",
    "referral_contacts",
    "linkedin_connection_imports",
    "linkedin_connections",
    "cloud_runs",
    "cloud_run_events",
)

_SEQUENCE_TABLES: tuple[str, ...] = tuple(
    table
    for table in MIGRATION_TABLE_ORDER
    if table not in {"cloud_runs"}
)


class HostedMigrationError(RuntimeError):
    pass


@dataclass(frozen=True)
class TableMigrationSummary:
    table: str
    source_rows: int
    copied_rows: int
    dry_run: bool


@dataclass(frozen=True)
class ResumeMigrationSummary:
    resume_asset_id: int
    source_uri: str
    destination_uri: str | None
    sha256: str
    byte_size: int
    dry_run: bool


@dataclass(frozen=True)
class HostedMigrationReport:
    status: str
    dry_run: bool
    source_db: str
    tables: tuple[TableMigrationSummary, ...]
    resumes: tuple[ResumeMigrationSummary, ...]
    checksums: dict[str, object]


def migrate_sqlite_to_postgres(
    *,
    source_db: str | Path,
    dry_run: bool = False,
    resume_asset_dir: str | Path | None = None,
    env: dict[str, str] | None = None,
) -> HostedMigrationReport:
    source = env if env is not None else os.environ
    sqlite_conn = connect(source_db)
    init_db(sqlite_conn)

    resume_summaries, storage_path_overrides = _plan_resume_migration(
        sqlite_conn,
        asset_dir=resume_asset_dir,
        env=source,
        dry_run=dry_run,
    )

    postgres_db: PostgresDatabase | None = None
    table_summaries: list[TableMigrationSummary] = []
    if dry_run:
        for table in MIGRATION_TABLE_ORDER:
            count = _sqlite_row_count(sqlite_conn, table)
            table_summaries.append(
                TableMigrationSummary(
                    table=table,
                    source_rows=count,
                    copied_rows=0,
                    dry_run=True,
                )
            )
    else:
        postgres_db = connect_from_env(source)
        apply_postgres_schema(postgres_db)
        _clear_postgres_tables(postgres_db)
        for table in MIGRATION_TABLE_ORDER:
            table_summaries.append(
                _copy_table(
                    sqlite_conn,
                    postgres_db,
                    table,
                    storage_path_overrides=storage_path_overrides,
                )
            )
        _reset_postgres_sequences(postgres_db)
        postgres_db.commit()

    checksums = validate_migration_checksums(
        sqlite_conn,
        postgres_db,
        resume_summaries=resume_summaries,
    )
    sqlite_conn.close()
    if postgres_db is not None:
        postgres_db.close()

    return HostedMigrationReport(
        status="dry_run" if dry_run else "ok",
        dry_run=dry_run,
        source_db=str(source_db),
        tables=tuple(table_summaries),
        resumes=tuple(resume_summaries),
        checksums=checksums,
    )


def validate_migration_checksums(
    sqlite_conn: sqlite3.Connection,
    postgres_db: PostgresDatabase | None,
    *,
    resume_summaries: tuple[ResumeMigrationSummary, ...] = (),
) -> dict[str, object]:
    table_counts = {
        table: _sqlite_row_count(sqlite_conn, table) for table in MIGRATION_TABLE_ORDER
    }
    destination_counts: dict[str, int | None] = {
        table: None for table in MIGRATION_TABLE_ORDER
    }
    mismatches: list[dict[str, object]] = []
    if postgres_db is not None:
        for table in MIGRATION_TABLE_ORDER:
            destination_counts[table] = _postgres_row_count(postgres_db, table)
            if destination_counts[table] != table_counts[table]:
                mismatches.append(
                    {
                        "table": table,
                        "source_rows": table_counts[table],
                        "destination_rows": destination_counts[table],
                    }
                )

    source_sha256 = {
        str(row["sha256"])
        for row in sqlite_conn.execute(
            "SELECT sha256 FROM resume_assets ORDER BY sha256"
        ).fetchall()
    }
    resume_checksum_matches = all(
        summary.sha256 in source_sha256 for summary in resume_summaries
    )

    return {
        "table_counts": table_counts,
        "destination_counts": destination_counts,
        "row_count_matches": not mismatches,
        "mismatches": mismatches,
        "resume_sha256_count": len(source_sha256),
        "resume_checksum_matches": resume_checksum_matches,
    }


def _plan_resume_migration(
    sqlite_conn: sqlite3.Connection,
    *,
    asset_dir: str | Path | None,
    env: dict[str, str],
    dry_run: bool,
) -> tuple[list[ResumeMigrationSummary], dict[int, str]]:
    local_storage = LocalResumeStorage(asset_dir=asset_dir)
    remote_storage = None
    summaries: list[ResumeMigrationSummary] = []
    overrides: dict[int, str] = {}
    rows = sqlite_conn.execute(
        """
        SELECT id, user_id, original_filename, storage_path, sha256
        FROM resume_assets
        ORDER BY id
        """
    ).fetchall()
    pending_local_resumes = [
        row
        for row in rows
        if str(row["storage_path"] or "").startswith(RESUME_ASSET_URI_PREFIX)
    ]
    if not dry_run and pending_local_resumes:
        backend = resume_storage_from_env(env, asset_dir=asset_dir)
        if not isinstance(backend, SupabaseResumeStorage):
            raise HostedMigrationError(
                "Resume file migration requires Supabase storage configuration"
            )
        remote_storage = backend

    for row in rows:
        storage_uri = str(row["storage_path"] or "")
        if storage_uri.startswith(SUPABASE_RESUME_URI_PREFIX):
            continue
        if not storage_uri.startswith(RESUME_ASSET_URI_PREFIX):
            raise HostedMigrationError(
                f"Unsupported resume storage URI for asset {row['id']}: {storage_uri}"
            )
        content = local_storage.load_bytes(storage_uri)
        digest = hashlib.sha256(content).hexdigest()
        if digest != str(row["sha256"]):
            raise HostedMigrationError(
                f"Resume checksum mismatch for asset {row['id']}: {storage_uri}"
            )
        destination_uri = None
        if not dry_run:
            assert remote_storage is not None
            destination_uri = remote_storage.persist(
                content,
                original_filename=str(row["original_filename"]),
                digest=digest,
                user_id=str(row["user_id"] or "") or None,
            )
            overrides[int(row["id"])] = destination_uri
        summaries.append(
            ResumeMigrationSummary(
                resume_asset_id=int(row["id"]),
                source_uri=storage_uri,
                destination_uri=destination_uri,
                sha256=digest,
                byte_size=len(content),
                dry_run=dry_run,
            )
        )
    return summaries, overrides


def _copy_table(
    sqlite_conn: sqlite3.Connection,
    postgres_db: PostgresDatabase,
    table: str,
    *,
    storage_path_overrides: dict[int, str],
) -> TableMigrationSummary:
    rows = sqlite_conn.execute(f'SELECT * FROM "{table}"').fetchall()
    if not rows:
        return TableMigrationSummary(table=table, source_rows=0, copied_rows=0, dry_run=False)

    columns = sorted(
        table_columns(sqlite_conn, table) & postgres_table_columns(postgres_db, table)
    )
    if not columns:
        raise HostedMigrationError(f"No shared columns found for table: {table}")

    placeholders = ", ".join("?" for _ in columns)
    column_sql = ", ".join(columns)
    sql = f"INSERT INTO {table} ({column_sql}) VALUES ({placeholders})"
    copied = 0
    for row in rows:
        values = []
        for column in columns:
            value = row[column]
            if table == "resume_assets" and column == "storage_path":
                override = storage_path_overrides.get(int(row["id"]))
                if override is not None:
                    value = override
            values.append(value)
        postgres_db.execute(sql, tuple(values))
        copied += 1
    postgres_db.commit()
    return TableMigrationSummary(
        table=table,
        source_rows=len(rows),
        copied_rows=copied,
        dry_run=False,
    )


def _clear_postgres_tables(postgres_db: PostgresDatabase) -> None:
    postgres_db.execute(
        "TRUNCATE "
        + ", ".join(MIGRATION_TABLE_ORDER)
        + " RESTART IDENTITY CASCADE"
    )
    postgres_db.commit()


def _reset_postgres_sequences(postgres_db: PostgresDatabase) -> None:
    for table in _SEQUENCE_TABLES:
        postgres_db.execute(
            f"""
            SELECT setval(
              pg_get_serial_sequence('{table}', 'id'),
              COALESCE((SELECT MAX(id) FROM {table}), 1),
              COALESCE((SELECT MAX(id) FROM {table}), 0) > 0
            )
            """
        )
    postgres_db.commit()


def _sqlite_row_count(conn: sqlite3.Connection, table: str) -> int:
    if table.replace("_", "").isalnum():
        row = conn.execute(f'SELECT COUNT(*) AS count FROM "{table}"').fetchone()
        return int(row["count"]) if row is not None else 0
    raise HostedMigrationError(f"Invalid table name: {table}")


def _postgres_row_count(conn: PostgresDatabase, table: str) -> int:
    if table.replace("_", "").isalnum():
        row = conn.execute(f"SELECT COUNT(*) AS count FROM {table}").fetchone()
        return int(row["count"]) if row is not None else 0
    raise HostedMigrationError(f"Invalid table name: {table}")