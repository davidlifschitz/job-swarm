from pathlib import Path

from fastapi.testclient import TestClient

from ml_job_swarm.app import create_app
from ml_job_swarm.filtering import review_jobs_for_profile, visible_company_results
from ml_job_swarm.ingest import RawJob, refresh_source
from ml_job_swarm.llm import FitGateResponse
from ml_job_swarm.profile import create_target_profile, update_preferences
from ml_job_swarm.resume_extract import parse_resume_text, record_parse_run
from ml_job_swarm.store import connect, init_db


FIXTURES = Path(__file__).parent / "fixtures"

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


class FakeAdapter:
    def __init__(self, jobs):
        self.jobs = jobs

    def fetch_jobs(self, source):
        return self.jobs


class FitGateByRulesClient:
    provider = "openrouter"
    model = "openrouter/test-fit-model"
    schema_version = "fit_gate.v1"

    def review_fit(self, payload):
        if "seniority_mismatch" in payload.rules_result["risks"]:
            return FitGateResponse(
                fit_score=45,
                label="Mismatch risk",
                reasons=["Skills overlap"],
                risks=["Experience level mismatch"],
                recommendation="Keep hidden unless expanded",
            )
        return FitGateResponse(
            fit_score=91,
            label="Strong fit",
            reasons=["Role, skills, and location match"],
            risks=[],
            recommendation="Prioritize",
        )


def test_daily_refresh_then_profile_matching_flow():
    conn, source_id = _db_with_source()
    refresh_source(conn, source_id, FakeAdapter([_raw_job("ml-platform")]))
    target_profile_id = _profile_from_resume(conn)

    review_ids = review_jobs_for_profile(conn, target_profile_id, FitGateByRulesClient())

    companies = visible_company_results(conn, target_profile_id)
    assert len(review_ids) == 1
    assert companies[0].name == "Example AI"
    assert [job.title for job in companies[0].visible_jobs] == [
        "Senior Machine Learning Engineer"
    ]


def test_seniority_mismatch_goes_to_mismatch_risks():
    conn, source_id = _db_with_source()
    refresh_source(conn, source_id, FakeAdapter([_raw_job("staff-risk")]))
    target_profile_id = _profile_from_resume(conn)

    review_jobs_for_profile(conn, target_profile_id, FitGateByRulesClient())

    companies = visible_company_results(conn, target_profile_id)
    assert companies[0].visible_jobs == []
    assert companies[0].mismatch_risk_count == 1
    assert companies[0].mismatch_risk_jobs[0].title == "Staff Machine Learning Engineer"


def test_profile_version_change_hides_old_fit_reviews():
    conn, source_id = _db_with_source()
    refresh_source(conn, source_id, FakeAdapter([_raw_job("ml-platform")]))
    target_profile_id = _profile_from_resume(conn)
    review_jobs_for_profile(conn, target_profile_id, FitGateByRulesClient())

    update_preferences(
        conn,
        target_profile_id,
        {
            **PREFERENCES,
            "location": {"answer": "San Francisco"},
        },
    )

    assert visible_company_results(conn, target_profile_id) == []


def test_policy_blocked_source_appears_in_admin_not_results():
    app = create_app()
    conn = app.state.conn
    source_id = _insert_company_source(conn, policy_mode="blocked")

    refresh_source(conn, source_id, FakeAdapter([_raw_job("ml-platform")]))
    target_profile_id = _profile_from_resume(conn)
    review_jobs_for_profile(conn, target_profile_id, FitGateByRulesClient())
    client = TestClient(app)

    dashboard = client.get(f"/dashboard?target_profile_id={target_profile_id}")
    admin = client.get("/admin/sources")
    assert "Senior Machine Learning Engineer" not in dashboard.text
    assert "policy_blocked" in admin.text
    assert "Example AI" in admin.text


def _db_with_source():
    conn = connect()
    init_db(conn)
    return conn, _insert_company_source(conn)


def _insert_company_source(conn, *, policy_mode="allowed"):
    company_id = conn.execute(
        """
        INSERT INTO companies (name, normalized_name, stage)
        VALUES (?, ?, ?)
        """,
        ("Example AI", "example ai", "growth"),
    ).lastrowid
    source_id = conn.execute(
        """
        INSERT INTO job_sources (
          company_id,
          url,
          source_type,
          policy_mode,
          review_status
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            company_id,
            "https://boards.greenhouse.io/example",
            "greenhouse",
            policy_mode,
            "reviewed",
        ),
    ).lastrowid
    conn.commit()
    return source_id


def _profile_from_resume(conn):
    resume_text = (FIXTURES / "resumes" / "ml_engineer.txt").read_text()
    resume_asset_id = conn.execute(
        """
        INSERT INTO resume_assets (original_filename, content_type, storage_path, sha256)
        VALUES (?, ?, ?, ?)
        """,
        ("resume.txt", "text/plain", "/tmp/resume.txt", f"sha-{id(conn)}"),
    ).lastrowid
    record_parse_run(conn, resume_asset_id, parse_resume_text(resume_text), None)
    return create_target_profile(conn, resume_asset_id, KEYWORDS, PREFERENCES)


def _raw_job(kind):
    if kind == "staff-risk":
        title = "Staff Machine Learning Engineer"
        seniority = "staff"
        description = (FIXTURES / "job_descriptions" / "seniority_risk.txt").read_text()
    else:
        title = "Senior Machine Learning Engineer"
        seniority = "senior"
        description = (FIXTURES / "job_descriptions" / "ml_platform.txt").read_text()
    return RawJob(
        external_id=kind,
        title=title,
        department="Engineering",
        location_text="Remote - New York, NY",
        remote_mode="remote",
        employment_type="full_time",
        seniority=seniority,
        description_text=description,
        requirements_text=description,
        apply_url=f"https://boards.greenhouse.io/example/jobs/{kind}",
        source_url=f"https://boards.greenhouse.io/example/jobs/{kind}",
    )
