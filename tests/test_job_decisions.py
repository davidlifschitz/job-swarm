import pytest

from ml_job_swarm.decisions import (
    clear_job_decision,
    record_job_decision,
    saved_job_export_rows,
)
from ml_job_swarm.filtering import visible_company_results
from ml_job_swarm.profile import create_target_profile
from ml_job_swarm.store import connect, init_db


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


def test_record_job_decision_upserts_by_job_and_profile_then_clears():
    conn = _db()
    job_id, target_profile_id = _seed_reviewed_job(conn)

    saved_id = record_job_decision(
        conn,
        job_id=job_id,
        target_profile_id=target_profile_id,
        decision="saved",
        notes="worth a call",
    )
    hidden_id = record_job_decision(
        conn,
        job_id=job_id,
        target_profile_id=target_profile_id,
        decision="hidden",
        notes="wrong team",
    )

    row = conn.execute(
        """
        SELECT id, decision, notes
        FROM job_decisions
        WHERE job_id = ? AND target_profile_id = ?
        """,
        (job_id, target_profile_id),
    ).fetchone()
    assert saved_id == hidden_id
    assert dict(row) == {"id": saved_id, "decision": "hidden", "notes": "wrong team"}

    clear_job_decision(conn, job_id=job_id, target_profile_id=target_profile_id)

    decision_count = conn.execute("SELECT COUNT(*) FROM job_decisions").fetchone()[0]
    assert decision_count == 0


def test_record_job_decision_rejects_invalid_decision():
    conn = _db()
    job_id, target_profile_id = _seed_reviewed_job(conn)

    with pytest.raises(ValueError, match="Invalid job decision"):
        record_job_decision(
            conn,
            job_id=job_id,
            target_profile_id=target_profile_id,
            decision="applied",
        )

    decision_count = conn.execute("SELECT COUNT(*) FROM job_decisions").fetchone()[0]
    assert decision_count == 0


def test_visible_results_mark_saved_jobs():
    conn = _db()
    job_id, target_profile_id = _seed_reviewed_job(conn)
    record_job_decision(
        conn,
        job_id=job_id,
        target_profile_id=target_profile_id,
        decision="saved",
        notes="ask about platform team",
    )

    companies = visible_company_results(conn, target_profile_id)

    assert companies[0].saved_count == 1
    assert companies[0].visible_jobs[0].decision == "saved"
    assert companies[0].visible_jobs[0].notes == "ask about platform team"
    assert companies[0].visible_jobs[0].title == "Senior Machine Learning Engineer"


def test_visible_results_move_hidden_jobs_to_hidden_section():
    conn = _db()
    job_id, target_profile_id = _seed_reviewed_job(conn)
    record_job_decision(
        conn,
        job_id=job_id,
        target_profile_id=target_profile_id,
        decision="hidden",
        notes="wrong seniority",
    )

    companies = visible_company_results(conn, target_profile_id)

    assert companies[0].visible_jobs == []
    assert companies[0].mismatch_risk_jobs == []
    assert companies[0].hidden_jobs[0].title == "Senior Machine Learning Engineer"
    assert companies[0].hidden_jobs[0].decision == "hidden"
    assert companies[0].hidden_jobs[0].notes == "wrong seniority"


def test_saved_job_export_rows_include_only_saved_jobs_for_profile():
    conn = _db()
    saved_job_id, target_profile_id = _seed_reviewed_job(
        conn,
        title="Saved ML Engineer",
    )
    hidden_job_id, _ = _seed_reviewed_job(
        conn,
        title="Hidden ML Engineer",
        target_profile_id=target_profile_id,
    )
    _seed_reviewed_job(
        conn,
        title="Unmarked ML Engineer",
        target_profile_id=target_profile_id,
    )
    other_profile_job_id, other_profile_id = _seed_reviewed_job(
        conn,
        title="Other Profile ML Engineer",
    )
    record_job_decision(
        conn,
        job_id=saved_job_id,
        target_profile_id=target_profile_id,
        decision="saved",
        notes="follow up with recruiter",
    )
    record_job_decision(
        conn,
        job_id=hidden_job_id,
        target_profile_id=target_profile_id,
        decision="hidden",
    )
    record_job_decision(
        conn,
        job_id=other_profile_job_id,
        target_profile_id=other_profile_id,
        decision="saved",
    )

    rows = saved_job_export_rows(conn, target_profile_id)

    assert [row["title"] for row in rows] == ["Saved ML Engineer"]
    assert rows[0]["company"] == "Example AI"
    assert rows[0]["fit_score"] == 90
    assert rows[0]["label"] == "Strong fit"
    assert rows[0]["decision"] == "saved"
    assert rows[0]["apply_url"] == ""
    assert rows[0]["notes"] == "follow up with recruiter"


def test_saved_job_export_rows_include_saved_job_without_fit_review():
    conn = _db()
    job_id, target_profile_id = _seed_unreviewed_job(conn)
    record_job_decision(
        conn,
        job_id=job_id,
        target_profile_id=target_profile_id,
        decision="saved",
        notes="public refresh candidate",
    )

    rows = saved_job_export_rows(conn, target_profile_id)

    assert [row["title"] for row in rows] == ["Public Refresh ML Engineer"]
    assert rows[0]["fit_score"] is None
    assert rows[0]["label"] == "Not reviewed"
    assert rows[0]["recommendation"] == ""
    assert rows[0]["notes"] == "public refresh candidate"


def _db():
    conn = connect()
    init_db(conn)
    return conn


def _seed_reviewed_job(
    conn,
    *,
    label="Strong fit",
    title="Senior Machine Learning Engineer",
    target_profile_id=None,
):
    if target_profile_id is None:
        resume_asset_id = conn.execute(
            """
            INSERT INTO resume_assets (original_filename, content_type, storage_path, sha256)
            VALUES (?, ?, ?, ?)
            """,
            ("resume.pdf", "application/pdf", "/tmp/resume.pdf", f"sha-{title}"),
        ).lastrowid
        target_profile_id = create_target_profile(
            conn,
            resume_asset_id=resume_asset_id,
            keywords=KEYWORDS,
            preferences=PREFERENCES,
        )
    company = conn.execute(
        "SELECT id FROM companies WHERE normalized_name = ?",
        ("example ai",),
    ).fetchone()
    if company is None:
        company_id = conn.execute(
            """
            INSERT INTO companies (name, normalized_name)
            VALUES (?, ?)
            """,
            ("Example AI", "example ai"),
        ).lastrowid
    else:
        company_id = company["id"]
    job_id = conn.execute(
        """
        INSERT INTO jobs (
          company_id,
          external_id,
          title,
          location_text,
          remote_mode,
          seniority,
          source_url,
          content_hash
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            company_id,
            f"decision-job-{title}",
            title,
            "Remote - New York, NY",
            "remote",
            "senior",
            "https://boards.greenhouse.io/example/jobs/1",
            f"hash-decision-job-{title}",
        ),
    ).lastrowid
    conn.execute(
        """
        INSERT INTO fit_reviews (
          job_id,
          target_profile_id,
          fit_score,
          label,
          reasons_json,
          risks_json,
          recommendation,
          profile_version
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            job_id,
            target_profile_id,
            90,
            label,
            '["matches role"]',
            "[]",
            "Review",
            1,
        ),
    )
    conn.commit()
    return job_id, target_profile_id


def _seed_unreviewed_job(conn):
    resume_asset_id = conn.execute(
        """
        INSERT INTO resume_assets (original_filename, content_type, storage_path, sha256)
        VALUES (?, ?, ?, ?)
        """,
        ("resume.pdf", "application/pdf", "/tmp/resume.pdf", "sha-unreviewed"),
    ).lastrowid
    target_profile_id = create_target_profile(
        conn,
        resume_asset_id=resume_asset_id,
        keywords=KEYWORDS,
        preferences=PREFERENCES,
    )
    company_id = conn.execute(
        """
        INSERT INTO companies (name, normalized_name)
        VALUES (?, ?)
        """,
        ("Example AI", "example ai"),
    ).lastrowid
    job_id = conn.execute(
        """
        INSERT INTO jobs (
          company_id,
          external_id,
          title,
          location_text,
          remote_mode,
          seniority,
          source_url,
          content_hash
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            company_id,
            "public-refresh-job",
            "Public Refresh ML Engineer",
            "Remote - New York, NY",
            "remote",
            "senior",
            "https://boards.greenhouse.io/example/jobs/public-refresh",
            "hash-public-refresh-job",
        ),
    ).lastrowid
    conn.commit()
    return job_id, target_profile_id
