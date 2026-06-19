from fastapi.testclient import TestClient

from ml_job_swarm.app import create_app
from ml_job_swarm.ingest import AdapterRegistry, RawJob
from ml_job_swarm.llm import FitGateResponse, ResumeRewriteResponse
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


class FakeFitGateClient:
    provider = "openrouter"
    model = "openrouter/test-fit-model"
    schema_version = "fit_gate.v1"

    def __init__(self):
        self.calls = []

    def review_fit(self, payload):
        self.calls.append(payload)
        return FitGateResponse(
            fit_score=91,
            label="Strong fit",
            reasons=["Role and skills fit"],
            risks=[],
            recommendation="Prioritize",
        )


class FakeRewriteClient:
    provider = "openrouter"
    model = "openrouter/test-rewrite-model"
    schema_version = "resume_rewrite.v1"

    def __init__(self):
        self.calls = []

    def rewrite_section(self, payload):
        self.calls.append(payload)
        return ResumeRewriteResponse(
            section_id=payload["section_id"],
            replacement_text="Built ML serving platform for 80M requests/day.",
            rationale="Uses stronger production impact.",
            risk_flags=[],
        )


class FakeAdapter:
    def __init__(self, jobs):
        self.jobs = jobs
        self.calls = []

    def fetch_jobs(self, source):
        self.calls.append(source)
        return self.jobs


def _seed_profile_and_source(conn):
    resume_asset_id = conn.execute(
        """
        INSERT INTO resume_assets (original_filename, content_type, storage_path, sha256)
        VALUES (?, ?, ?, ?)
        """,
        ("resume.pdf", "application/pdf", "/tmp/resume.pdf", "api-v1-llm-sha"),
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
    conn.execute(
        """
        INSERT INTO job_sources (
          company_id, url, source_type, policy_mode, review_status
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
    conn.commit()
    return target_profile_id


def _seed_profile_with_section(conn):
    resume_asset_id = conn.execute(
        """
        INSERT INTO resume_assets (original_filename, content_type, storage_path, sha256)
        VALUES (?, ?, ?, ?)
        """,
        ("resume.pdf", "application/pdf", "/tmp/resume.pdf", "api-v1-rewrite-sha"),
    ).lastrowid
    parse_run_id = conn.execute(
        """
        INSERT INTO resume_parse_runs (
          resume_asset_id, parser, parser_version, status, confidence
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (resume_asset_id, "text", "v1", "succeeded", 0.91),
    ).lastrowid
    section_id = conn.execute(
        """
        INSERT INTO resume_sections (parse_run_id, section_type, heading, text, sort_order)
        VALUES (?, ?, ?, ?, ?)
        """,
        (parse_run_id, "experience", "Experience", "Built ML systems.", 1),
    ).lastrowid
    target_profile_id = create_target_profile(
        conn,
        resume_asset_id=resume_asset_id,
        keywords=KEYWORDS,
        preferences=PREFERENCES,
    )
    conn.commit()
    return target_profile_id, int(section_id)


def _raw_job():
    return RawJob(
        external_id="senior-ml-engineer",
        title="Senior Machine Learning Engineer",
        department="Engineering",
        location_text="Remote - New York, NY",
        remote_mode="remote",
        employment_type="Full-time",
        seniority="senior",
        description_text="Build ML ranking systems with Python and PyTorch.",
        requirements_text="Python, PyTorch, and model serving.",
        apply_url="https://boards.greenhouse.io/example/jobs/1",
        source_url="https://boards.greenhouse.io/example/jobs/1",
    )


def test_api_v1_health_reports_fit_review_when_client_configured():
    app = create_app()
    app.state.fit_gate_client = FakeFitGateClient()
    client = TestClient(app)

    health = client.get("/api/v1/health")

    assert health.status_code == 200
    assert health.json()["fit_review_available"] is True


def test_api_v1_find_matches_requires_llm_consent():
    app = create_app()
    target_profile_id = _seed_profile_and_source(app.state.conn)
    app.state.fit_gate_client = FakeFitGateClient()
    client = TestClient(app)

    response = client.post(
        "/api/v1/dashboard/find-matches",
        json={"target_profile_id": target_profile_id, "llm_consent": False},
    )

    assert response.status_code == 400
    assert "LLM consent" in response.json()["detail"]


def test_api_v1_find_matches_refreshes_and_reviews_with_mock_client():
    app = create_app()
    target_profile_id = _seed_profile_and_source(app.state.conn)
    adapter = FakeAdapter([_raw_job()])
    fit_client = FakeFitGateClient()
    app.state.adapter_registry = AdapterRegistry({"greenhouse": adapter})
    app.state.fit_gate_client = fit_client
    client = TestClient(app)

    response = client.post(
        "/api/v1/dashboard/find-matches",
        json={"target_profile_id": target_profile_id, "llm_consent": True},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["review"] is not None
    assert payload["review"]["review_ids"]
    assert len(adapter.calls) == 1


def test_api_v1_find_matches_refresh_only_without_client():
    app = create_app()
    target_profile_id = _seed_profile_and_source(app.state.conn)
    app.state.fit_gate_client = None
    client = TestClient(app)

    response = client.post(
        "/api/v1/dashboard/find-matches",
        json={"target_profile_id": target_profile_id, "llm_consent": True},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "refresh_only"
    assert response.json()["review"] is None


def _seed_reviewable_job(conn):
    target_profile_id = _seed_profile_and_source(conn)
    company_id = conn.execute("SELECT company_id FROM job_sources LIMIT 1").fetchone()[
        "company_id"
    ]
    conn.execute(
        """
        INSERT INTO jobs (
          company_id, external_id, title, department, location_text, remote_mode,
          employment_type, seniority, description_text, requirements_text,
          apply_url, source_url, content_hash, status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            company_id,
            "api-v1-llm-job",
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
            "api-v1-llm-job-hash",
            "open",
        ),
    )
    conn.commit()
    return target_profile_id


def test_api_v1_review_jobs_invokes_mock_llm_client():
    app = create_app()
    target_profile_id = _seed_reviewable_job(app.state.conn)
    fit_client = FakeFitGateClient()
    app.state.fit_gate_client = fit_client
    client = TestClient(app)

    response = client.post(
        "/api/v1/dashboard/review-jobs",
        json={"target_profile_id": target_profile_id, "llm_consent": True},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert len(fit_client.calls) == 1

    dashboard = client.get(f"/api/v1/dashboard?target_profile_id={target_profile_id}")
    assert dashboard.status_code == 200
    assert len(dashboard.json()["companies"]) == 1


def test_api_v1_resume_rewrite_with_mock_client():
    app = create_app()
    target_profile_id, section_id = _seed_profile_with_section(app.state.conn)
    rewrite_client = FakeRewriteClient()
    app.state.resume_rewrite_client = rewrite_client
    client = TestClient(app)

    response = client.post(
        f"/api/v1/profiles/{target_profile_id}/resume/rewrite",
        json={
            "section_id": section_id,
            "target_profile_id": target_profile_id,
            "llm_consent": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["suggestion_id"] > 0
    assert "80M requests" in payload["suggestion_text"]
    assert len(rewrite_client.calls) == 1


def test_api_v1_resume_rewrite_requires_client():
    app = create_app()
    target_profile_id, section_id = _seed_profile_with_section(app.state.conn)
    client = TestClient(app)

    response = client.post(
        f"/api/v1/profiles/{target_profile_id}/resume/rewrite",
        json={
            "section_id": section_id,
            "target_profile_id": target_profile_id,
            "llm_consent": True,
        },
    )

    assert response.status_code == 503
    assert "unavailable" in response.json()["detail"].casefold()


def test_api_v1_openrouter_env_configures_clients(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "unit-test-token")
    monkeypatch.setenv("OPENROUTER_FIT_MODEL", "openrouter/fit-test")
    monkeypatch.setenv("OPENROUTER_RESUME_REWRITE_MODEL", "openrouter/rewrite-test")
    monkeypatch.setenv("OPENROUTER_VISION_MODEL", "openrouter/vision-test")

    from ml_job_swarm.app import create_app_from_env

    app = create_app_from_env()
    client = TestClient(app)

    health = client.get("/api/v1/health")

    assert health.status_code == 200
    assert health.json()["fit_review_available"] is True
    assert app.state.fit_gate_client is not None
    assert app.state.resume_rewrite_client is not None
    assert app.state.vision_fallback_provider is not None
    assert app.state.fit_gate_client.model == "openrouter/fit-test"


def test_api_v1_llm_usage_endpoint_reports_audit_log():
    app = create_app()
    client = TestClient(app)

    empty = client.get("/api/v1/llm/usage")
    assert empty.status_code == 200
    assert empty.json()["total_requests"] == 0
    assert empty.json()["recent_requests"] == []

    target_profile_id = _seed_reviewable_job(app.state.conn)
    app.state.fit_gate_client = FakeFitGateClient()
    review = client.post(
        "/api/v1/dashboard/review-jobs",
        json={"target_profile_id": target_profile_id, "llm_consent": True},
    )
    assert review.status_code == 200

    usage = client.get("/api/v1/llm/usage")
    assert usage.status_code == 200
    payload = usage.json()
    assert payload["total_requests"] >= 1
    assert "fit_gate" in payload["by_feature"]
    assert payload["by_feature"]["fit_gate"]["succeeded"] >= 1
    assert payload["recent_requests"][0]["feature"] == "fit_gate"
    assert payload["recent_requests"][0]["status"] == "succeeded"