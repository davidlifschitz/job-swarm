import os

import pytest

from ml_job_swarm.db.factory import connect_from_env
from ml_job_swarm.db.postgres_backend import PostgresDatabase
from ml_job_swarm.decisions import record_job_decision
from ml_job_swarm.linkedin_connections import LinkedInConnection, import_linkedin_connections
from ml_job_swarm.profile import (
    ProfileAccessDenied,
    ResumeAssetAccessDenied,
    create_target_profile,
    require_resume_asset_access,
    require_target_profile_access,
    upsert_resume_asset_record,
)
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
    reason="Set ML_JOB_SWARM_TEST_DATABASE_URL to run Postgres per-user tests",
)


@pytest.fixture
def postgres_conn(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", POSTGRES_URL)
    db = connect_from_env()
    assert isinstance(db, PostgresDatabase)
    for table in (
        "preference_answers",
        "target_profiles",
        "resume_assets",
        "linkedin_connections",
        "linkedin_connection_imports",
        "job_decisions",
        "application_packets",
        "fit_reviews",
        "rules_filter_results",
    ):
        db.execute(f"DELETE FROM {table}")
    db.execute("DELETE FROM jobs")
    db.execute("DELETE FROM companies")
    db.commit()
    init_db(db)
    yield db
    db.close()


def _seed_company_and_job(conn) -> int:
    company_id = conn.execute(
        """
        INSERT INTO companies (name, normalized_name, status)
        VALUES ('Acme', 'acme', 'active')
        RETURNING id
        """
    ).fetchone()["id"]
    job_id = conn.execute(
        """
        INSERT INTO jobs (
          company_id,
          title,
          source_url,
          apply_url,
          status
        )
        VALUES (?, 'ML Engineer', 'https://jobs.lever.co/acme/1', 'https://jobs.lever.co/acme/1', 'open')
        """,
        (company_id,),
    ).lastrowid
    return int(job_id)


def test_postgres_resume_assets_are_scoped_per_user(postgres_conn):
    asset_a = upsert_resume_asset_record(
        postgres_conn,
        user_id="user-a",
        original_filename="a.pdf",
        content_type="application/pdf",
        storage_path="supabase://resume-assets/user-a/a.pdf",
        sha256="sha-a",
    )
    asset_b = upsert_resume_asset_record(
        postgres_conn,
        user_id="user-b",
        original_filename="b.pdf",
        content_type="application/pdf",
        storage_path="supabase://resume-assets/user-b/b.pdf",
        sha256="sha-b",
    )
    assert asset_a != asset_b

    require_resume_asset_access(postgres_conn, asset_a, user_id="user-a")
    with pytest.raises(ResumeAssetAccessDenied):
        require_resume_asset_access(postgres_conn, asset_b, user_id="user-a")


def test_postgres_target_profiles_and_decisions_are_user_scoped(postgres_conn):
    asset_a = upsert_resume_asset_record(
        postgres_conn,
        user_id="user-a",
        original_filename="a.pdf",
        content_type="application/pdf",
        storage_path="supabase://resume-assets/user-a/a.pdf",
        sha256="sha-profile-a",
    )
    asset_b = upsert_resume_asset_record(
        postgres_conn,
        user_id="user-b",
        original_filename="b.pdf",
        content_type="application/pdf",
        storage_path="supabase://resume-assets/user-b/b.pdf",
        sha256="sha-profile-b",
    )
    profile_a = create_target_profile(
        postgres_conn,
        asset_a,
        KEYWORDS,
        PREFERENCES,
        user_id="user-a",
    )
    profile_b = create_target_profile(
        postgres_conn,
        asset_b,
        KEYWORDS,
        PREFERENCES,
        user_id="user-b",
    )

    require_target_profile_access(postgres_conn, profile_a, user_id="user-a")
    with pytest.raises(ProfileAccessDenied):
        require_target_profile_access(postgres_conn, profile_b, user_id="user-a")

    job_id = _seed_company_and_job(postgres_conn)
    decision_id = record_job_decision(
        postgres_conn,
        job_id=job_id,
        target_profile_id=profile_a,
        decision="saved",
        notes="referral path",
    )
    assert decision_id > 0


def test_postgres_linkedin_imports_are_user_scoped(postgres_conn):
    connections = [
        LinkedInConnection(
            first_name="Ada",
            last_name="Lovelace",
            profile_url="https://www.linkedin.com/in/ada",
            company="Analytical Engines",
            position="Engineer",
            connected_on="01 Jan 2020",
        )
    ]
    result_a = import_linkedin_connections(
        postgres_conn,
        connections=connections,
        filename="a.csv",
        user_id="user-a",
    )
    result_b = import_linkedin_connections(
        postgres_conn,
        connections=connections,
        filename="b.csv",
        user_id="user-b",
    )
    assert result_a.import_id != result_b.import_id
    count_a = postgres_conn.execute(
        "SELECT COUNT(*) AS count FROM linkedin_connections WHERE user_id = ?",
        ("user-a",),
    ).fetchone()["count"]
    count_b = postgres_conn.execute(
        "SELECT COUNT(*) AS count FROM linkedin_connections WHERE user_id = ?",
        ("user-b",),
    ).fetchone()["count"]
    assert count_a == 1
    assert count_b == 1