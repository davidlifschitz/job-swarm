import hashlib
import json
import os
from pathlib import Path

import pytest

from ml_job_swarm.hosted_migration import (
    MIGRATION_TABLE_ORDER,
    HostedMigrationError,
    migrate_sqlite_to_postgres,
    validate_migration_checksums,
)
from ml_job_swarm.resume_assets import RESUME_ASSET_URI_PREFIX
from ml_job_swarm.store import connect, init_db

POSTGRES_URL = os.environ.get("ML_JOB_SWARM_TEST_DATABASE_URL", "")


def _seed_sqlite(path: Path, *, resume_dir: Path) -> None:
    conn = connect(path)
    init_db(conn)
    company_id = conn.execute(
        """
        INSERT INTO companies (name, normalized_name, stage)
        VALUES ('Migration Co', 'migration co', 'growth')
        """
    ).lastrowid
    conn.execute(
        """
        INSERT INTO jobs (
          company_id, external_id, title, source_url, content_hash, status
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            company_id,
            "migration-role",
            "Migration Engineer",
            "https://example.com/jobs/migration",
            "migration-hash",
            "open",
        ),
    )
    resume_dir.mkdir(parents=True, exist_ok=True)
    pdf_bytes = b"%PDF-1.4\nmigration resume\n%%EOF\n"
    digest = hashlib.sha256(pdf_bytes).hexdigest()
    filename = f"{digest}.pdf"
    (resume_dir / filename).write_bytes(pdf_bytes)
    conn.execute(
        """
        INSERT INTO resume_assets (
          user_id,
          original_filename,
          content_type,
          storage_path,
          sha256
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            "user-a",
            "resume.pdf",
            "application/pdf",
            f"{RESUME_ASSET_URI_PREFIX}{filename}",
            digest,
        ),
    )
    conn.commit()
    conn.close()


def test_migration_table_order_covers_foundation_schema():
    assert "companies" in MIGRATION_TABLE_ORDER
    assert MIGRATION_TABLE_ORDER.index("llm_requests") < MIGRATION_TABLE_ORDER.index(
        "fit_reviews"
    )
    assert MIGRATION_TABLE_ORDER.index("resume_assets") < MIGRATION_TABLE_ORDER.index(
        "target_profiles"
    )


def test_dry_run_reports_source_counts_without_destination_writes(tmp_path):
    source_db = tmp_path / "source.db"
    resume_dir = tmp_path / "resume-assets"
    _seed_sqlite(source_db, resume_dir=resume_dir)

    report = migrate_sqlite_to_postgres(
        source_db=source_db,
        dry_run=True,
        resume_asset_dir=resume_dir,
    )

    assert report.status == "dry_run"
    assert report.checksums["row_count_matches"] is True
    companies = next(summary for summary in report.tables if summary.table == "companies")
    jobs = next(summary for summary in report.tables if summary.table == "jobs")
    assert companies.source_rows == 1
    assert jobs.source_rows == 1
    assert len(report.resumes) == 1
    assert report.resumes[0].byte_size > 0


def test_dry_run_rejects_resume_checksum_mismatch(tmp_path):
    source_db = tmp_path / "source.db"
    resume_dir = tmp_path / "resume-assets"
    _seed_sqlite(source_db, resume_dir=resume_dir)
    conn = connect(source_db)
    conn.execute("UPDATE resume_assets SET sha256 = 'bad-checksum'")
    conn.commit()
    conn.close()

    with pytest.raises(HostedMigrationError, match="checksum mismatch"):
        migrate_sqlite_to_postgres(
            source_db=source_db,
            dry_run=True,
            resume_asset_dir=resume_dir,
        )


@pytest.mark.skipif(
    not POSTGRES_URL,
    reason="Set ML_JOB_SWARM_TEST_DATABASE_URL to run Postgres migration tests",
)
def test_migrate_sqlite_to_postgres_copies_rows_and_validates_checksums(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("DATABASE_URL", POSTGRES_URL)
    source_db = tmp_path / "source.db"
    resume_dir = tmp_path / "resume-assets"
    _seed_sqlite(source_db, resume_dir=resume_dir)

    report = migrate_sqlite_to_postgres(
        source_db=source_db,
        dry_run=True,
        resume_asset_dir=resume_dir,
    )
    assert report.checksums["resume_checksum_matches"] is True

    sqlite_conn = connect(source_db)
    checksums = validate_migration_checksums(sqlite_conn)
    sqlite_conn.close()
    assert checksums["table_counts"]["jobs"] == 1
    assert checksums["resume_sha256_count"] == 1