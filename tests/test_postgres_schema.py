import os

import pytest

from ml_job_swarm.db.factory import connect_from_env
from ml_job_swarm.db.postgres_backend import PostgresDatabase
from ml_job_swarm.store import init_db, table_columns

POSTGRES_URL = os.environ.get("ML_JOB_SWARM_TEST_DATABASE_URL", "")

EXPECTED_TABLES = {
    "companies",
    "job_sources",
    "company_source_review_queue",
    "ingestion_runs",
    "source_friction_events",
    "admin_audit_events",
    "cloud_runs",
    "cloud_run_events",
    "job_snapshots",
    "jobs",
    "resume_assets",
    "resume_parse_runs",
    "resume_sections",
    "resume_keywords",
    "target_profiles",
    "preference_answers",
    "resume_rewrite_suggestions",
    "rules_filter_results",
    "fit_reviews",
    "llm_requests",
    "job_decisions",
    "application_packets",
    "contacts",
    "referral_contacts",
    "linkedin_connection_imports",
    "linkedin_connections",
}


pytestmark = pytest.mark.skipif(
    not POSTGRES_URL,
    reason="Set ML_JOB_SWARM_TEST_DATABASE_URL to run Postgres schema tests",
)


@pytest.fixture
def postgres_db(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", POSTGRES_URL)
    db = connect_from_env()
    assert isinstance(db, PostgresDatabase)
    for table in EXPECTED_TABLES:
        db.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
    db.commit()
    init_db(db)
    yield db
    db.close()


def test_postgres_init_db_creates_foundation_tables(postgres_db):
    from ml_job_swarm.db.postgres_schema import list_postgres_tables

    table_names = list_postgres_tables(postgres_db)
    assert EXPECTED_TABLES <= table_names


def test_postgres_schema_includes_user_scoped_columns(postgres_db):
    assert {"user_id", "sha256", "storage_path"} <= table_columns(
        postgres_db, "resume_assets"
    )
    assert {"user_id", "profile_url"} <= table_columns(
        postgres_db, "linkedin_connections"
    )
    assert {"user_id", "trace_id"} <= table_columns(postgres_db, "cloud_runs")


def test_postgres_init_db_is_idempotent(postgres_db):
    init_db(postgres_db)
    init_db(postgres_db)
    row = postgres_db.execute("SELECT COUNT(*) AS count FROM companies").fetchone()
    assert int(row["count"]) == 0