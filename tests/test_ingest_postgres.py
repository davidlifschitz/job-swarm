import os

import pytest

from ml_job_swarm.db.factory import connect_from_env
from ml_job_swarm.db.postgres_backend import PostgresDatabase
from ml_job_swarm.ingest import RawJob, refresh_source
from ml_job_swarm.store import init_db

POSTGRES_URL = os.environ.get("ML_JOB_SWARM_TEST_DATABASE_URL", "")

pytestmark = pytest.mark.skipif(
    not POSTGRES_URL,
    reason="Set ML_JOB_SWARM_TEST_DATABASE_URL to run Postgres ingest tests",
)


class FakeAdapter:
    def fetch_jobs(self, source):
        return [
            RawJob(
                external_id="pg-job-1",
                title="Postgres ML Engineer",
                department="Engineering",
                location_text="Remote",
                remote_mode="remote",
                employment_type="full_time",
                seniority="senior",
                description_text="Build models",
                requirements_text="Python",
                apply_url="https://boards.greenhouse.io/example/jobs/pg-job-1",
                source_url="https://boards.greenhouse.io/example/jobs/pg-job-1",
            )
        ]


@pytest.fixture
def postgres_conn(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", POSTGRES_URL)
    db = connect_from_env()
    assert isinstance(db, PostgresDatabase)
    init_db(db)
    for table in (
        "job_snapshots",
        "source_friction_events",
        "jobs",
        "ingestion_runs",
        "job_sources",
        "companies",
    ):
        db.execute(f"DELETE FROM {table}")
    db.commit()
    company_id = db.execute(
        """
        INSERT INTO companies (name, normalized_name, careers_url, ats_type)
        VALUES ('Example AI', 'example ai', 'https://boards.greenhouse.io/example', 'greenhouse')
        RETURNING id
        """
    ).fetchone()["id"]
    source_id = db.execute(
        """
        INSERT INTO job_sources (
          company_id,
          url,
          source_type,
          policy_mode,
          review_status
        )
        VALUES (?, ?, 'greenhouse', 'allowed', 'reviewed')
        """,
        (company_id, "https://boards.greenhouse.io/example"),
    ).lastrowid
    db.commit()
    yield db, int(source_id)
    db.close()


def test_postgres_refresh_source_records_jobs_and_snapshots(postgres_conn):
    conn, source_id = postgres_conn

    result = refresh_source(conn, source_id, FakeAdapter())

    assert result.status == "succeeded"
    assert result.jobs_seen == 1
    assert result.jobs_added == 1
    run = conn.execute("SELECT status, jobs_seen FROM ingestion_runs").fetchone()
    assert run["status"] == "succeeded"
    assert run["jobs_seen"] == 1
    assert conn.execute("SELECT COUNT(*) AS count FROM jobs").fetchone()["count"] == 1
    assert conn.execute("SELECT COUNT(*) AS count FROM job_snapshots").fetchone()["count"] == 1


def test_postgres_refresh_due_sources_summarizes_fixture_adapters(postgres_conn, monkeypatch):
    conn, source_id = postgres_conn
    from ml_job_swarm.ingest import refresh_due_sources

    class FakeAdapter:
        def fetch_jobs(self, source):
            return [
                RawJob(
                    external_id="pg-due-1",
                    title="Postgres Due ML Engineer",
                    department="Engineering",
                    location_text="Remote",
                    remote_mode="remote",
                    employment_type="full_time",
                    seniority="senior",
                    description_text="Build models",
                    requirements_text="Python",
                    apply_url="https://boards.greenhouse.io/example/jobs/pg-due-1",
                    source_url="https://boards.greenhouse.io/example/jobs/pg-due-1",
                )
            ]

    conn.execute(
        """
        UPDATE job_sources
        SET last_refreshed_at = NULL, review_status = 'reviewed', policy_mode = 'allowed'
        WHERE id = ?
        """,
        (source_id,),
    )
    conn.commit()

    summary = refresh_due_sources(conn, AdapterRegistry({"greenhouse": FakeAdapter()}))

    assert summary.sources_attempted >= 1
    assert summary.sources_succeeded >= 1
    assert summary.jobs_seen >= 1