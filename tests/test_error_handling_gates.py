from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import pytest
from fastapi.testclient import TestClient

from ml_job_swarm.app import create_app
from ml_job_swarm.ingest import AdapterRegistry, RefreshError
from ml_job_swarm.llm import FitGateResponse
from ml_job_swarm.profile import create_target_profile


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


class StrongFitGateClient:
    provider = "openrouter"
    model = "openrouter/test-fit-model"
    schema_version = "fit_gate.v1"

    def review_fit(self, _payload):
        return FitGateResponse(
            fit_score=93,
            label="Strong fit",
            reasons=["Role and skills fit"],
            risks=[],
            recommendation="Prioritize",
        )


class FailingRefreshAdapter:
    def fetch_jobs(self, _source):
        raise RefreshError(
            "blocked by source",
            "blocked_response",
            status_code=403,
        )


def _seed_profile(conn) -> int:
    resume_asset_id = conn.execute(
        """
        INSERT INTO resume_assets (original_filename, content_type, storage_path, sha256)
        VALUES (?, ?, ?, ?)
        """,
        ("resume.pdf", "application/pdf", "/tmp/resume.pdf", "error-gate-sha"),
    ).lastrowid
    return create_target_profile(
        conn,
        resume_asset_id=resume_asset_id,
        keywords=KEYWORDS,
        preferences=PREFERENCES,
    )


def _seed_profile_and_source(app) -> int:
    target_profile_id = _seed_profile(app.state.conn)
    company_id = app.state.conn.execute(
        """
        INSERT INTO companies (name, normalized_name, stage)
        VALUES (?, ?, ?)
        """,
        ("Example AI", "example ai", "growth"),
    ).lastrowid
    app.state.conn.execute(
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
            "allowed",
            "reviewed",
        ),
    )
    app.state.conn.commit()
    return target_profile_id


def _seed_profile_and_failing_source(app) -> int:
    target_profile_id = _seed_profile_and_source(app)
    app.state.adapter_registry = AdapterRegistry(
        {"greenhouse": FailingRefreshAdapter()}
    )
    return target_profile_id


def _seed_reviewable_job(app) -> int:
    target_profile_id = _seed_profile(app.state.conn)
    company_id = app.state.conn.execute(
        """
        INSERT INTO companies (name, normalized_name, stage)
        VALUES (?, ?, ?)
        """,
        ("Example AI", "example ai", "growth"),
    ).lastrowid
    app.state.conn.execute(
        """
        INSERT INTO jobs (
          company_id,
          external_id,
          title,
          department,
          location_text,
          remote_mode,
          employment_type,
          seniority,
          description_text,
          requirements_text,
          apply_url,
          source_url,
          content_hash
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            company_id,
            "error-gate-job",
            "Senior Machine Learning Engineer",
            "Engineering",
            "Remote - New York, NY",
            "remote",
            "Full-time",
            "senior",
            "Build ML ranking systems with Python and PyTorch.",
            "Python, PyTorch, and model serving.",
            "https://boards.greenhouse.io/example/jobs/1",
            "https://boards.greenhouse.io/example/jobs/1",
            "error-gate-hash",
        ),
    )
    app.state.conn.commit()
    return target_profile_id


@dataclass(frozen=True)
class ErrorGateCase:
    case_id: str
    method: str
    path: str
    form_data: dict[str, str] | None
    expected_status: int
    expected_html: tuple[str, ...]
    setup: Callable | None = None
    follow_redirects: bool = False
    assert_no_hidden_state: Callable | None = None


ERROR_GATE_CASES = [
    ErrorGateCase(
        case_id="no_resume",
        method="post",
        path="/preferences",
        form_data={
            "role": "Machine Learning Engineer",
            "level": "senior",
            "location": "New York",
            "work_mode": "remote",
            "company_stage": "growth",
        },
        expected_status=400,
        expected_html=(
            'action="/preferences"',
            "Upload a resume",
        ),
    ),
    ErrorGateCase(
        case_id="no_resume_dashboard",
        method="get",
        path="/dashboard",
        form_data=None,
        expected_status=200,
        expected_html=(
            "Upload resume",
            'href="/onboarding"',
            "Open onboarding",
        ),
    ),
    ErrorGateCase(
        case_id="no_profile",
        method="get",
        path="/dashboard",
        form_data=None,
        expected_status=200,
        expected_html=(
            "Complete preferences before matching",
            'href="/onboarding"',
            "Open onboarding",
        ),
    ),
    ErrorGateCase(
        case_id="no_profile_invalid_target",
        method="get",
        path="/dashboard?target_profile_id=99999",
        form_data=None,
        expected_status=200,
        expected_html=(
            "Complete preferences before matching",
            'href="/onboarding"',
            'href="/admin/sources"',
        ),
        setup=lambda app: None,
    ),
    ErrorGateCase(
        case_id="no_llm_consent_find_matches",
        method="post",
        path="/dashboard/find-matches",
        form_data={"target_profile_id": "{target_profile_id}"},
        expected_status=400,
        expected_html=("LLM consent is required",),
        setup=_seed_profile_and_source,
        assert_no_hidden_state=lambda conn: (
            conn.execute("SELECT COUNT(*) FROM fit_reviews").fetchone()[0] == 0
        ),
    ),
    ErrorGateCase(
        case_id="no_llm_consent_review_jobs",
        method="post",
        path="/dashboard/review-jobs",
        form_data={"target_profile_id": "{target_profile_id}"},
        expected_status=400,
        expected_html=("LLM consent is required",),
        setup=_seed_reviewable_job,
        assert_no_hidden_state=lambda conn: (
            conn.execute("SELECT COUNT(*) FROM fit_reviews").fetchone()[0] == 0
        ),
    ),
    ErrorGateCase(
        case_id="source_failure",
        method="post",
        path="/dashboard/refresh-sources",
        form_data={"target_profile_id": "{target_profile_id}"},
        expected_status=200,
        expected_html=(
            "completed with failures",
            "Failures",
            'href="/admin/sources"',
            'action="/dashboard/refresh-sources"',
            "Refresh public sources",
        ),
        setup=_seed_profile_and_failing_source,
        follow_redirects=True,
        assert_no_hidden_state=lambda conn: (
            conn.execute("SELECT COUNT(*) FROM ingestion_runs").fetchone()[0] >= 1
            and conn.execute("SELECT COUNT(*) FROM source_friction_events").fetchone()[0]
            >= 1
        ),
    ),
]


@pytest.mark.parametrize("case", ERROR_GATE_CASES, ids=[case.case_id for case in ERROR_GATE_CASES])
def test_error_handling_gate_matrix(case: ErrorGateCase):
    app = create_app()
    target_profile_id = None
    if case.setup is not None:
        target_profile_id = case.setup(app)
        if case.case_id.startswith("no_llm_consent"):
            app.state.fit_gate_client = StrongFitGateClient()

    client = TestClient(app)
    form_data = _resolve_form_data(case.form_data, target_profile_id)

    if case.method == "get":
        response = client.get(case.path, follow_redirects=case.follow_redirects)
    else:
        response = client.post(
            case.path,
            data=form_data,
            follow_redirects=case.follow_redirects,
        )

    assert response.status_code == case.expected_status
    for fragment in case.expected_html:
        assert fragment in response.text, (
            f"{case.case_id}: expected {fragment!r} in HTML response"
        )

    if case.assert_no_hidden_state is not None:
        assert case.assert_no_hidden_state(app.state.conn), (
            f"{case.case_id}: hidden partial state detected"
        )


def _resolve_form_data(
    form_data: dict[str, str] | None,
    target_profile_id: int | None,
) -> dict[str, str] | None:
    if form_data is None:
        return None
    resolved = {}
    for key, value in form_data.items():
        if value == "{target_profile_id}":
            assert target_profile_id is not None
            resolved[key] = str(target_profile_id)
        else:
            resolved[key] = value
    return resolved

