import json

import pytest
from pydantic import ValidationError

from ml_job_swarm.filtering import (
    rules_preview_jobs,
    review_candidate_job,
    review_jobs_for_profile_resilient,
    visible_company_results,
)
from ml_job_swarm.llm import FitGateResponse
from ml_job_swarm.profile import create_target_profile, update_preferences
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


class FakeFitGateClient:
    provider = "openrouter"
    model = "openrouter/test-fit-model"
    schema_version = "fit_gate.v1"

    def __init__(self, response):
        self.response = response
        self.calls = []

    def review_fit(self, payload):
        self.calls.append(payload)
        return self.response


class NoCallFitGateClient:
    provider = "openrouter"
    model = "openrouter/test-fit-model"
    schema_version = "fit_gate.v1"

    def review_fit(self, payload):
        raise AssertionError("rules-rejected jobs must not call the LLM")


class ErrorFitGateClient:
    provider = "openrouter"
    model = "openrouter/test-fit-model"
    schema_version = "fit_gate.v1"

    def review_fit(self, payload):
        raise RuntimeError("provider timeout")


class TitleSensitiveFitGateClient:
    provider = "openrouter"
    model = "openrouter/test-fit-model"
    schema_version = "fit_gate.v1"

    def review_fit(self, payload):
        if "Failing" in payload.job["title"]:
            raise RuntimeError("provider timeout")
        return _fit_response(label="Strong fit", score=91)


def test_strong_fit_is_visible():
    conn, target_profile_id, job_id = _db_with_profile_and_job()
    client = FakeFitGateClient(
        {
            "fit_score": 92,
            "label": "Strong fit",
            "reasons": ["Strong ML platform match"],
            "risks": [],
            "recommendation": "Prioritize",
        }
    )

    review_candidate_job(conn, job_id, target_profile_id, client)

    companies = visible_company_results(conn, target_profile_id)
    assert len(companies) == 1
    assert companies[0].name == "Example AI"
    assert companies[0].mismatch_risk_count == 0
    assert companies[0].filtered_out_count == 0
    assert [job.label for job in companies[0].visible_jobs] == ["Strong fit"]
    assert companies[0].visible_jobs[0].fit_score == 92


def test_closed_jobs_are_hidden_from_visible_company_results():
    conn, target_profile_id, job_id = _db_with_profile_and_job()
    review_candidate_job(
        conn,
        job_id,
        target_profile_id,
        FakeFitGateClient(_fit_response(label="Strong fit", score=92)),
    )
    conn.execute("UPDATE jobs SET status = 'closed' WHERE id = ?", (job_id,))
    conn.commit()

    assert visible_company_results(conn, target_profile_id) == []


def test_rules_preview_jobs_ranks_unreviewed_candidates_without_persisting_reviews():
    conn, target_profile_id, job_id = _db_with_profile_and_job()

    previews = rules_preview_jobs(conn, target_profile_id)

    assert len(previews) == 1
    preview = previews[0]
    assert preview.job_id == job_id
    assert preview.company_name == "Example AI"
    assert preview.title == "Senior Machine Learning Engineer"
    assert preview.outcome == "pass"
    assert preview.score >= 80
    assert "role_match" in preview.reasons
    assert conn.execute("SELECT COUNT(*) FROM fit_reviews").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM rules_filter_results").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM llm_requests").fetchone()[0] == 0


def test_rules_preview_jobs_excludes_obvious_mismatches():
    conn, target_profile_id, _job_id = _db_with_profile_and_job(
        title="Office Manager",
        description_text="Coordinate office supplies and schedules.",
        requirements_text="Vendor management and facilities coordination.",
    )

    assert rules_preview_jobs(conn, target_profile_id) == []


def test_possible_fit_is_visible():
    conn, target_profile_id, job_id = _db_with_profile_and_job()
    client = FakeFitGateClient(_fit_response(label="Possible fit", score=74))

    review_candidate_job(conn, job_id, target_profile_id, client)

    companies = visible_company_results(conn, target_profile_id)
    assert [job.label for job in companies[0].visible_jobs] == ["Possible fit"]
    assert companies[0].mismatch_risk_count == 0


def test_mismatch_risk_is_hidden_by_default():
    conn, target_profile_id, job_id = _db_with_profile_and_job()
    client = FakeFitGateClient(_fit_response(label="Mismatch risk", score=49))

    review_candidate_job(conn, job_id, target_profile_id, client)

    companies = visible_company_results(conn, target_profile_id)
    assert companies[0].visible_jobs == []
    assert companies[0].mismatch_risk_count == 1
    assert [job.label for job in companies[0].mismatch_risk_jobs] == ["Mismatch risk"]


def test_filtered_out_is_stored_not_visible():
    conn, target_profile_id, job_id = _db_with_profile_and_job(
        title="Product Marketing Manager",
        description_text="Own messaging, positioning, and campaigns.",
        requirements_text="Marketing launches and content strategy.",
    )
    client = NoCallFitGateClient()

    review_id = review_candidate_job(conn, job_id, target_profile_id, client)

    review = conn.execute(
        "SELECT label, fit_score, llm_request_id FROM fit_reviews WHERE id = ?",
        (review_id,),
    ).fetchone()
    companies = visible_company_results(conn, target_profile_id)
    assert review["label"] == "Filtered out"
    assert review["llm_request_id"] is None
    assert companies[0].visible_jobs == []
    assert companies[0].filtered_out_count == 1


def test_fit_review_records_current_profile_version():
    conn, target_profile_id, job_id = _db_with_profile_and_job()
    update_preferences(
        conn,
        target_profile_id,
        {
            **PREFERENCES,
            "work_mode": {"answer": "hybrid"},
        },
    )

    review_id = review_candidate_job(
        conn,
        job_id,
        target_profile_id,
        FakeFitGateClient(_fit_response()),
    )

    review = conn.execute(
        "SELECT profile_version FROM fit_reviews WHERE id = ?",
        (review_id,),
    ).fetchone()
    assert review["profile_version"] == 2


def test_fit_review_records_llm_request_id():
    conn, target_profile_id, job_id = _db_with_profile_and_job()

    review_id = review_candidate_job(
        conn,
        job_id,
        target_profile_id,
        FakeFitGateClient(_fit_response()),
    )

    review = conn.execute(
        "SELECT llm_request_id FROM fit_reviews WHERE id = ?",
        (review_id,),
    ).fetchone()
    llm_request = conn.execute(
        "SELECT feature, schema_version, status, response_json FROM llm_requests WHERE id = ?",
        (review["llm_request_id"],),
    ).fetchone()
    persisted = json.dumps(dict(llm_request), sort_keys=True)
    assert review["llm_request_id"] is not None
    assert llm_request["feature"] == "fit_gate"
    assert llm_request["schema_version"] == "fit_gate.v1"
    assert llm_request["status"] == "succeeded"
    assert "PRIVATE RESUME" not in persisted


def test_invalid_fit_gate_response_records_failed_llm_request():
    conn, target_profile_id, job_id = _db_with_profile_and_job()
    client = FakeFitGateClient(
        {
            "fit_score": "not-a-score",
            "label": "Strong fit",
            "reasons": ["bad"],
            "risks": [],
            "recommendation": "bad",
            "raw_resume_text": "PRIVATE RESUME",
        }
    )

    with pytest.raises(ValidationError):
        review_candidate_job(conn, job_id, target_profile_id, client)

    request = conn.execute("SELECT * FROM llm_requests").fetchone()
    persisted = json.dumps(dict(request), sort_keys=True)
    assert request["feature"] == "fit_gate"
    assert request["status"] == "failed"
    assert "not-a-score" in persisted
    assert "PRIVATE RESUME" not in persisted


def test_fit_gate_client_exception_records_failed_llm_request():
    conn, target_profile_id, job_id = _db_with_profile_and_job()

    with pytest.raises(RuntimeError, match="provider timeout"):
        review_candidate_job(conn, job_id, target_profile_id, ErrorFitGateClient())

    request = conn.execute("SELECT feature, status, error FROM llm_requests").fetchone()
    assert dict(request) == {
        "feature": "fit_gate",
        "status": "failed",
        "error": "provider timeout",
    }


def test_resilient_profile_review_continues_after_per_job_failure():
    conn, target_profile_id, _job_id = _db_with_profile_and_job(
        title="Failing Machine Learning Engineer"
    )
    _insert_additional_job(conn, title="Senior Machine Learning Engineer")

    result = review_jobs_for_profile_resilient(
        conn,
        target_profile_id,
        TitleSensitiveFitGateClient(),
    )

    companies = visible_company_results(conn, target_profile_id)
    failed_requests = conn.execute(
        "SELECT status, error FROM llm_requests WHERE status = 'failed'"
    ).fetchall()
    assert result.failures == 1
    assert len(result.review_ids) == 1
    assert [job.title for job in companies[0].visible_jobs] == [
        "Senior Machine Learning Engineer"
    ]
    assert [dict(row) for row in failed_requests] == [
        {"status": "failed", "error": "provider timeout"}
    ]


def _db_with_profile_and_job(
    *,
    title="Senior Machine Learning Engineer",
    description_text="Build reliable ML systems with Python and PyTorch.",
    requirements_text="Python, PyTorch, model serving, and LLM evaluation.",
):
    conn = connect()
    init_db(conn)
    resume_asset_id = conn.execute(
        """
        INSERT INTO resume_assets (original_filename, content_type, storage_path, sha256)
        VALUES (?, ?, ?, ?)
        """,
        ("resume.pdf", "application/pdf", "/tmp/resume.pdf", "resume-sha"),
    ).lastrowid
    target_profile_id = create_target_profile(
        conn,
        resume_asset_id=resume_asset_id,
        keywords=KEYWORDS,
        preferences=PREFERENCES,
    )
    company_id = conn.execute(
        """
        INSERT INTO companies (name, normalized_name, stage)
        VALUES (?, ?, ?)
        """,
        ("Example AI", "example ai", "growth"),
    ).lastrowid
    source_id = conn.execute(
        """
        INSERT INTO job_sources (company_id, url, source_type, policy_mode, review_status)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            company_id,
            "https://boards.greenhouse.io/example",
            "greenhouse",
            "allowed",
            "reviewed",
        ),
    ).lastrowid
    job_id = conn.execute(
        """
        INSERT INTO jobs (
          company_id,
          job_source_id,
          external_id,
          title,
          location_text,
          remote_mode,
          seniority,
          description_text,
          requirements_text,
          apply_url,
          source_url,
          content_hash
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            company_id,
            source_id,
            f"job-{title}",
            title,
            "Remote - New York, NY",
            "remote",
            "senior",
            description_text,
            requirements_text,
            "https://boards.greenhouse.io/example/jobs/1",
            "https://boards.greenhouse.io/example/jobs/1",
            f"hash-{title}",
        ),
    ).lastrowid
    conn.commit()
    return conn, target_profile_id, job_id


def _insert_additional_job(conn, *, title: str):
    source = conn.execute(
        """
        SELECT job_sources.id AS source_id, companies.id AS company_id
        FROM job_sources
        JOIN companies ON companies.id = job_sources.company_id
        LIMIT 1
        """
    ).fetchone()
    conn.execute(
        """
        INSERT INTO jobs (
          company_id,
          job_source_id,
          external_id,
          title,
          location_text,
          remote_mode,
          seniority,
          description_text,
          requirements_text,
          apply_url,
          source_url,
          content_hash
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            source["company_id"],
            source["source_id"],
            f"job-{title}",
            title,
            "Remote - New York, NY",
            "remote",
            "senior",
            "Build reliable ML systems with Python and PyTorch.",
            "Python, PyTorch, model serving, and LLM evaluation.",
            "https://boards.greenhouse.io/example/jobs/2",
            "https://boards.greenhouse.io/example/jobs/2",
            f"hash-{title}",
        ),
    )
    conn.commit()


def _fit_response(label="Strong fit", score=88):
    return FitGateResponse(
        fit_score=score,
        label=label,
        reasons=["Role and skills fit"],
        risks=[] if label != "Mismatch risk" else ["Experience depth uncertain"],
        recommendation="Review",
    )
