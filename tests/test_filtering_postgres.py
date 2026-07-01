import os

import pytest

from ml_job_swarm.db.factory import connect_from_env
from ml_job_swarm.db.postgres_backend import PostgresDatabase
from ml_job_swarm.filtering import rules_preview_jobs
from ml_job_swarm.profile import create_target_profile
from ml_job_swarm.store import init_db

POSTGRES_URL = os.environ.get("ML_JOB_SWARM_TEST_DATABASE_URL", "")

PREFERENCES = {
    "role": {"answer": "Machine Learning Engineer"},
    "level": {"answer": "senior"},
    "location": {"answer": "New York"},
    "work_mode": {"answer": "remote"},
    "company_stage": {"answer": "growth"},
}

KEYWORDS = {
    "desired_titles": ["Machine Learning Engineer"],
    "levels": ["senior"],
    "locations": ["New York"],
    "remote_modes": ["remote"],
    "company_stages": ["growth"],
}

pytestmark = pytest.mark.skipif(
    not POSTGRES_URL,
    reason="Set ML_JOB_SWARM_TEST_DATABASE_URL to run Postgres filtering tests",
)


@pytest.fixture
def postgres_conn(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", POSTGRES_URL)
    db = connect_from_env()
    assert isinstance(db, PostgresDatabase)
    init_db(db)
    for table in (
        "fit_reviews",
        "rules_filter_results",
        "llm_requests",
        "job_decisions",
        "jobs",
        "job_sources",
        "companies",
        "target_profiles",
        "resume_assets",
    ):
        db.execute(f"DELETE FROM {table}")
    db.commit()
    yield db
    db.close()


def test_postgres_rules_preview_jobs_ranks_candidates_without_persisting_reviews(postgres_conn):
    resume_asset_id = postgres_conn.execute(
        """
        INSERT INTO resume_assets (original_filename, content_type, storage_path, sha256)
        VALUES ('resume.pdf', 'application/pdf', '/tmp/resume.pdf', 'pg-filter-resume')
        RETURNING id
        """
    ).fetchone()["id"]
    target_profile_id = create_target_profile(
        postgres_conn,
        resume_asset_id=int(resume_asset_id),
        keywords=KEYWORDS,
        preferences=PREFERENCES,
    )
    company_id = postgres_conn.execute(
        """
        INSERT INTO companies (name, normalized_name, stage)
        VALUES ('Example AI', 'example ai', 'growth')
        RETURNING id
        """
    ).fetchone()["id"]
    postgres_conn.execute(
        """
        INSERT INTO job_sources (
          company_id, url, source_type, policy_mode, review_status
        )
        VALUES (?, 'https://boards.greenhouse.io/example', 'greenhouse', 'allowed', 'reviewed')
        """,
        (company_id,),
    )
    postgres_conn.execute(
        """
        INSERT INTO jobs (
          company_id, external_id, title, location_text, remote_mode, seniority,
          description_text, requirements_text, source_url, content_hash, status
        )
        VALUES (?, 'pg-1', 'Senior Machine Learning Engineer', 'Remote - New York, NY', 'remote',
                'senior', 'Build ML systems with Python and PyTorch.',
                'Python, PyTorch, and model serving.',
                'https://boards.greenhouse.io/example/jobs/pg-1', 'pg-filter-hash', 'open')
        """,
        (company_id,),
    )
    postgres_conn.commit()

    previews = rules_preview_jobs(postgres_conn, target_profile_id)

    assert len(previews) == 1
    assert previews[0].title == "Senior Machine Learning Engineer"
    assert previews[0].outcome == "pass"
    assert (
        postgres_conn.execute("SELECT COUNT(*) AS count FROM rules_filter_results").fetchone()[
            "count"
        ]
        == 0
    )
