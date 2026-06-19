import json
import os
from pathlib import Path

import pytest

from ml_job_swarm.catalog import import_seed_companies, review_company_source, submit_company_source
from ml_job_swarm.db.factory import connect_from_env
from ml_job_swarm.db.postgres_backend import PostgresDatabase
from ml_job_swarm.store import init_db

POSTGRES_URL = os.environ.get("ML_JOB_SWARM_TEST_DATABASE_URL", "")

pytestmark = pytest.mark.skipif(
    not POSTGRES_URL,
    reason="Set ML_JOB_SWARM_TEST_DATABASE_URL to run Postgres catalog tests",
)


@pytest.fixture
def postgres_conn(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", POSTGRES_URL)
    db = connect_from_env()
    assert isinstance(db, PostgresDatabase)
    for table in (
        "admin_audit_events",
        "job_snapshots",
        "source_friction_events",
        "jobs",
        "ingestion_runs",
        "job_sources",
        "company_source_review_queue",
        "companies",
    ):
        db.execute(f"DELETE FROM {table}")
    db.commit()
    init_db(db)
    yield db
    db.close()


def _write_seed(path: Path) -> None:
    path.write_text(
        json.dumps(
            [
                {
                    "name": "Postgres Seed Co",
                    "aliases": ["PSC"],
                    "tags": ["ai_infra"],
                    "stage": "growth",
                    "priority_tier": 2,
                    "careers_url": "https://boards.greenhouse.io/postgres-seed",
                    "ats_type": "greenhouse",
                    "reviewed_at": "2026-06-19",
                    "extra_sources": [],
                }
            ]
        )
    )


def test_postgres_import_seed_companies_is_idempotent(postgres_conn, tmp_path):
    seed_path = tmp_path / "seed.json"
    _write_seed(seed_path)

    first = import_seed_companies(postgres_conn, seed_path)
    second = import_seed_companies(postgres_conn, seed_path)

    assert first == 1
    assert second == 0
    count = postgres_conn.execute("SELECT COUNT(*) AS count FROM companies").fetchone()["count"]
    source_count = postgres_conn.execute(
        "SELECT COUNT(*) AS count FROM job_sources"
    ).fetchone()["count"]
    assert count == 1
    assert source_count == 1


def test_postgres_review_company_source_creates_shared_catalog_rows(postgres_conn):
    queue_id = submit_company_source(
        postgres_conn,
        "Reviewed Postgres Co",
        "https://boards.greenhouse.io/reviewed-postgres",
    )
    result = review_company_source(postgres_conn, queue_id, action="approve")

    assert result["status"] == "approved"
    assert result["job_source_id"] is not None
    company = postgres_conn.execute(
        "SELECT normalized_name FROM companies WHERE id = (SELECT company_id FROM job_sources WHERE id = ?)",
        (result["job_source_id"],),
    ).fetchone()
    assert company["normalized_name"] == "reviewed postgres co"