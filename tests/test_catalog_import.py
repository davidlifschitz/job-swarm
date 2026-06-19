import sqlite3
from pathlib import Path

from ml_job_swarm.catalog_import import import_job_catalog
from ml_job_swarm.store import connect, init_db


def _seed_legacy_db(path: Path) -> None:
    conn = connect(path)
    init_db(conn)
    company_id = conn.execute(
        """
        INSERT INTO companies (name, normalized_name, stage)
        VALUES (?, ?, ?)
        """,
        ("Legacy Co", "legacy co", "growth"),
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
            "legacy-role",
            "Legacy Engineer",
            "https://example.com/jobs/legacy",
            "legacy-hash",
            "open",
        ),
    )
    conn.commit()
    conn.close()


def test_import_job_catalog_copies_jobs_when_destination_empty(tmp_path: Path):
    legacy = tmp_path / "legacy.db"
    destination = tmp_path / "destination.db"
    _seed_legacy_db(legacy)

    conn = connect(destination)
    init_db(conn)
    summary = import_job_catalog(conn, legacy)
    conn.close()

    assert summary["status"] == "ok"
    imported = connect(destination)
    count = imported.execute("SELECT COUNT(*) AS count FROM jobs").fetchone()["count"]
    imported.close()
    assert count == 1


def test_import_job_catalog_skips_when_destination_has_jobs(tmp_path: Path):
    legacy = tmp_path / "legacy.db"
    destination = tmp_path / "destination.db"
    _seed_legacy_db(legacy)
    _seed_legacy_db(destination)

    conn = connect(destination)
    summary = import_job_catalog(conn, legacy)
    conn.close()

    assert summary["status"] == "skipped"
    assert summary["reason"] == "destination_has_jobs"