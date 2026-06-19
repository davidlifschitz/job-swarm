import json

import pytest

from ml_job_swarm.profile import (
    REQUIRED_PREFERENCE_IDS,
    create_target_profile,
    current_profile_version,
    update_preferences,
)
from ml_job_swarm.store import connect, init_db


KEYWORDS = {
    "desired_titles": ["Machine Learning Engineer"],
    "levels": ["senior"],
    "locations": ["New York"],
    "remote_modes": ["remote"],
    "company_stages": ["growth"],
}


PREFERENCES = {
    "role": {"answer": "Machine Learning Engineer"},
    "level": {"answer": "senior"},
    "location": {"answer": "New York"},
    "work_mode": {"answer": "remote"},
    "company_stage": {"answer": "growth"},
}


@pytest.fixture()
def conn():
    conn = connect()
    init_db(conn)
    try:
        yield conn
    finally:
        conn.close()


def insert_resume_asset(conn):
    cursor = conn.execute(
        """
        INSERT INTO resume_assets (original_filename, content_type, storage_path, sha256)
        VALUES (?, ?, ?, ?)
        """,
        ("resume.pdf", "application/pdf", "/tmp/resume.pdf", "resume-sha"),
    )
    conn.commit()
    return cursor.lastrowid


def test_create_target_profile_version_one(conn):
    resume_asset_id = insert_resume_asset(conn)

    target_profile_id = create_target_profile(
        conn,
        resume_asset_id=resume_asset_id,
        keywords=KEYWORDS,
        preferences=PREFERENCES,
    )

    profile = conn.execute(
        """
        SELECT version, resume_asset_id, desired_titles_json, active
        FROM target_profiles
        WHERE id = ?
        """,
        (target_profile_id,),
    ).fetchone()
    assert profile["version"] == 1
    assert profile["resume_asset_id"] == resume_asset_id
    assert profile["active"] == 1
    assert json.loads(profile["desired_titles_json"]) == ["Machine Learning Engineer"]
    assert current_profile_version(conn, target_profile_id) == 1

    answers = {
        row["question_key"]: json.loads(row["answer_json"])
        for row in conn.execute(
            """
            SELECT question_key, answer_json
            FROM preference_answers
            WHERE target_profile_id = ?
            """,
            (target_profile_id,),
        )
    }
    assert list(REQUIRED_PREFERENCE_IDS) == [
        "role",
        "level",
        "location",
        "work_mode",
        "company_stage",
    ]
    assert answers == PREFERENCES


def test_preference_update_increments_profile_version(conn):
    resume_asset_id = insert_resume_asset(conn)
    target_profile_id = create_target_profile(conn, resume_asset_id, KEYWORDS, PREFERENCES)
    updated_preferences = {
        **PREFERENCES,
        "work_mode": {"answer": "hybrid"},
    }

    new_version = update_preferences(conn, target_profile_id, updated_preferences)

    assert new_version == 2
    assert current_profile_version(conn, target_profile_id) == 2
    answer = conn.execute(
        """
        SELECT answer_json
        FROM preference_answers
        WHERE target_profile_id = ? AND question_key = 'work_mode'
        """,
        (target_profile_id,),
    ).fetchone()
    assert json.loads(answer["answer_json"]) == {"answer": "hybrid"}
    profile = conn.execute(
        """
        SELECT remote_modes_json
        FROM target_profiles
        WHERE id = ?
        """,
        (target_profile_id,),
    ).fetchone()
    assert json.loads(profile["remote_modes_json"]) == ["hybrid"]


def test_fixed_question_ids_are_required(conn):
    resume_asset_id = insert_resume_asset(conn)

    missing_role = dict(PREFERENCES)
    missing_role.pop("role")
    with pytest.raises(ValueError, match="missing.*role"):
        create_target_profile(conn, resume_asset_id, KEYWORDS, missing_role)

    target_profile_id = create_target_profile(conn, resume_asset_id, KEYWORDS, PREFERENCES)
    extra_salary = {
        **PREFERENCES,
        "salary": {"answer": "200000"},
    }
    with pytest.raises(ValueError, match="extra.*salary"):
        update_preferences(conn, target_profile_id, extra_salary)


def test_old_fit_reviews_do_not_match_current_profile_version(conn):
    resume_asset_id = insert_resume_asset(conn)
    target_profile_id = create_target_profile(conn, resume_asset_id, KEYWORDS, PREFERENCES)
    company_id = conn.execute(
        """
        INSERT INTO companies (name, normalized_name)
        VALUES (?, ?)
        """,
        ("Acme AI", "acme-ai"),
    ).lastrowid
    job_id = conn.execute(
        """
        INSERT INTO jobs (company_id, title, source_url, content_hash)
        VALUES (?, ?, ?, ?)
        """,
        (company_id, "Senior ML Engineer", "https://example.com/jobs/1", "job-sha"),
    ).lastrowid
    old_review_id = conn.execute(
        """
        INSERT INTO fit_reviews (
            job_id,
            target_profile_id,
            fit_score,
            label,
            recommendation,
            profile_version
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (job_id, target_profile_id, 92, "strong_fit", "review", 1),
    ).lastrowid
    conn.commit()

    update_preferences(
        conn,
        target_profile_id,
        {
            **PREFERENCES,
            "location": {"answer": "San Francisco"},
        },
    )
    current_version = current_profile_version(conn, target_profile_id)

    current_reviews = conn.execute(
        """
        SELECT id
        FROM fit_reviews
        WHERE target_profile_id = ? AND profile_version = ?
        """,
        (target_profile_id, current_version),
    ).fetchall()
    old_review = conn.execute(
        "SELECT id, profile_version FROM fit_reviews WHERE id = ?",
        (old_review_id,),
    ).fetchone()

    assert current_version == 2
    assert current_reviews == []
    assert old_review["profile_version"] == 1
