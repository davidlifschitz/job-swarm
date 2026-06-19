from fastapi.testclient import TestClient

from ml_job_swarm.app import create_app
from ml_job_swarm.ingest import AdapterRegistry, RawJob
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


class FailingFitGateClient:
    provider = "openrouter"
    model = "openrouter/test-fit-model"
    schema_version = "fit_gate.v1"

    def review_fit(self, _payload):
        raise RuntimeError("provider timeout")


class StrongFitGateClient:
    provider = "openrouter"
    model = "openrouter/test-fit-model"
    schema_version = "fit_gate.v1"

    def __init__(self):
        self.calls = []

    def review_fit(self, payload):
        self.calls.append(payload)
        if "Failing" in payload.job["title"]:
            raise RuntimeError("provider timeout")
        return FitGateResponse(
            fit_score=93,
            label="Strong fit",
            reasons=["Role and skills fit"],
            risks=[],
            recommendation="Prioritize",
        )


class FakeAdapter:
    def __init__(self, jobs):
        self.jobs = jobs
        self.calls = []

    def fetch_jobs(self, source):
        self.calls.append(source)
        return self.jobs


def test_dashboard_find_matches_refreshes_sources_and_reviews_jobs():
    app = create_app()
    target_profile_id = _seed_profile_and_source(app.state.conn)
    adapter = FakeAdapter([_raw_job()])
    fit_client = StrongFitGateClient()
    app.state.adapter_registry = AdapterRegistry({"greenhouse": adapter})
    app.state.fit_gate_client = fit_client
    client = TestClient(app)

    response = client.post(
        "/dashboard/find-matches",
        data={"target_profile_id": target_profile_id, "llm_consent": "on"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    location = response.headers["location"]
    assert location.startswith(f"/dashboard?target_profile_id={target_profile_id}")
    assert "match_status=completed" in location
    assert "sources_attempted=1" in location
    assert "sources_succeeded=1" in location
    assert "sources_refreshed=1" in location
    assert "jobs_seen=1" in location
    assert "jobs_closed=0" in location
    assert "reviews_created=1" in location
    assert "failures=0" in location
    assert len(adapter.calls) == 1
    assert len(fit_client.calls) == 1

    dashboard = client.get(location)
    assert dashboard.status_code == 200
    assert "Match run completed" in dashboard.text
    assert "Senior Machine Learning Engineer" in dashboard.text


def test_dashboard_find_matches_continues_after_one_fit_review_failure():
    app = create_app()
    target_profile_id = _seed_profile_and_source(app.state.conn)
    adapter = FakeAdapter(
        [_raw_job(title="Failing Machine Learning Engineer"), _raw_job()]
    )
    fit_client = StrongFitGateClient()
    app.state.adapter_registry = AdapterRegistry({"greenhouse": adapter})
    app.state.fit_gate_client = fit_client
    client = TestClient(app)

    response = client.post(
        "/dashboard/find-matches",
        data={"target_profile_id": target_profile_id, "llm_consent": "on"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    location = response.headers["location"]
    assert "match_status=failed" in location
    assert "reviews_created=1" in location
    assert "review_failures=1" in location
    dashboard = client.get(location)
    assert dashboard.status_code == 200
    assert "Senior Machine Learning Engineer" in dashboard.text
    assert "Review failures" in dashboard.text


def test_dashboard_empty_state_offers_find_matches_action():
    app = create_app()
    target_profile_id = _seed_profile_and_source(app.state.conn)
    client = TestClient(app)

    response = client.get(f"/dashboard?target_profile_id={target_profile_id}")

    assert response.status_code == 200
    assert "No current matches" in response.text
    assert 'action="/dashboard/refresh-sources"' in response.text
    assert "Refresh public sources" in response.text
    assert 'action="/dashboard/find-matches"' in response.text
    assert "Find matches" in response.text
    assert "I consent to send job/profile fit-review content" in response.text


def test_dashboard_shows_fit_review_unavailable_state_without_client():
    app = create_app()
    target_profile_id = _seed_profile_and_source(app.state.conn)
    app.state.fit_gate_client = None
    client = TestClient(app)

    response = client.get(f"/dashboard?target_profile_id={target_profile_id}")

    assert response.status_code == 200
    assert "LLM fit review unavailable" in response.text
    assert '<button type="submit" disabled>Find matches</button>' in response.text
    assert '<button type="submit" disabled>Run fit review</button>' in response.text
    assert '<button type="submit">Refresh public sources</button>' in response.text


def test_dashboard_enables_fit_review_actions_when_client_available():
    app = create_app()
    target_profile_id = _seed_profile_and_source(app.state.conn)
    app.state.fit_gate_client = StrongFitGateClient()
    client = TestClient(app)

    response = client.get(f"/dashboard?target_profile_id={target_profile_id}")

    assert response.status_code == 200
    assert "LLM fit review unavailable" not in response.text
    assert '<button type="submit">Find matches</button>' in response.text
    assert '<button type="submit">Run fit review</button>' in response.text


def test_dashboard_lists_jobs_waiting_for_fit_review():
    app = create_app()
    target_profile_id = _seed_reviewable_job(app.state.conn)
    client = TestClient(app)

    response = client.get(f"/dashboard?target_profile_id={target_profile_id}")

    assert response.status_code == 200
    assert "Jobs waiting for fit review" in response.text
    assert "Senior Machine Learning Engineer" in response.text
    assert "Example AI" in response.text
    assert f"/jobs/1?target_profile_id={target_profile_id}" in response.text


def test_dashboard_does_not_list_current_reviewed_jobs_as_waiting():
    app = create_app()
    target_profile_id = _seed_reviewed_match(app.state.conn)
    client = TestClient(app)

    response = client.get(f"/dashboard?target_profile_id={target_profile_id}")

    assert response.status_code == 200
    assert "Senior Machine Learning Engineer" in response.text
    assert "Jobs waiting for fit review" not in response.text


def test_dashboard_rules_preview_without_llm_client():
    app = create_app()
    target_profile_id = _seed_reviewable_job(app.state.conn)
    app.state.fit_gate_client = None
    client = TestClient(app)

    response = client.get(f"/dashboard?target_profile_id={target_profile_id}")

    assert response.status_code == 200
    assert "Rules preview" in response.text
    assert "Senior Machine Learning Engineer" in response.text
    assert "Example AI" in response.text
    assert "role_match" in response.text
    assert app.state.conn.execute("SELECT COUNT(*) FROM fit_reviews").fetchone()[0] == 0
    assert (
        app.state.conn.execute("SELECT COUNT(*) FROM rules_filter_results").fetchone()[0]
        == 0
    )
    assert app.state.conn.execute("SELECT COUNT(*) FROM llm_requests").fetchone()[0] == 0


def test_dashboard_refresh_sources_does_not_require_llm_consent_or_client():
    app = create_app()
    target_profile_id = _seed_profile_and_source(app.state.conn)
    adapter = FakeAdapter([_raw_job()])
    app.state.adapter_registry = AdapterRegistry({"greenhouse": adapter})
    app.state.fit_gate_client = None
    client = TestClient(app)

    response = client.post(
        "/dashboard/refresh-sources",
        data={"target_profile_id": target_profile_id},
        follow_redirects=False,
    )

    assert response.status_code == 303
    location = response.headers["location"]
    assert location.startswith(f"/dashboard?target_profile_id={target_profile_id}")
    assert "refresh_status=completed" in location
    assert "sources_attempted=1" in location
    assert "sources_succeeded=1" in location
    assert "sources_refreshed=1" in location
    assert "jobs_seen=1" in location
    assert "jobs_closed=0" in location
    assert "suspicious_empty=0" in location
    assert "reviews_created=0" in location
    assert len(adapter.calls) == 1
    assert app.state.conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 1

    dashboard = client.get(location)
    assert dashboard.status_code == 200
    assert "Source refresh completed" in dashboard.text
    assert "Sources attempted" in dashboard.text
    assert "Sources succeeded" in dashboard.text
    assert "Jobs seen" in dashboard.text
    assert "Jobs closed" in dashboard.text
    assert "Suspicious empty" in dashboard.text


def test_dashboard_refresh_sources_reports_suspicious_empty_sources():
    app = create_app()
    target_profile_id = _seed_profile_and_source(app.state.conn)
    adapter = FakeAdapter([])
    app.state.adapter_registry = AdapterRegistry({"greenhouse": adapter})
    client = TestClient(app)

    response = client.post(
        "/dashboard/refresh-sources",
        data={"target_profile_id": target_profile_id},
        follow_redirects=False,
    )

    assert response.status_code == 303
    location = response.headers["location"]
    assert "refresh_status=completed" in location
    assert "sources_attempted=1" in location
    assert "sources_succeeded=0" in location
    assert "sources_refreshed=0" in location
    assert "jobs_seen=0" in location
    assert "suspicious_empty=1" in location
    dashboard = client.get(location)
    assert "Suspicious empty" in dashboard.text


def test_public_refresh_job_can_be_saved_and_prepared_without_fit_review():
    app = create_app()
    target_profile_id = _seed_profile_and_source(app.state.conn)
    adapter = FakeAdapter([_raw_job()])
    app.state.adapter_registry = AdapterRegistry({"greenhouse": adapter})
    app.state.fit_gate_client = None
    client = TestClient(app)

    refresh = client.post(
        "/dashboard/refresh-sources",
        data={"target_profile_id": target_profile_id},
        follow_redirects=False,
    )
    job_id = app.state.conn.execute("SELECT id FROM jobs").fetchone()["id"]
    dashboard = client.get(refresh.headers["location"])

    assert dashboard.status_code == 200
    assert "Rules preview" in dashboard.text
    assert "Jobs waiting for fit review" in dashboard.text
    assert f'action="/jobs/{job_id}/decision"' in dashboard.text

    save = client.post(
        f"/jobs/{job_id}/decision",
        data={
            "target_profile_id": target_profile_id,
            "decision": "saved",
            "notes": "no-credential shortlist",
            "return_to": f"/dashboard?target_profile_id={target_profile_id}",
        },
        follow_redirects=False,
    )
    saved = client.get(f"/dashboard/saved?target_profile_id={target_profile_id}")
    csv_response = client.get(
        f"/dashboard/saved.csv?target_profile_id={target_profile_id}"
    )

    assert save.status_code == 303
    assert "Senior Machine Learning Engineer" in saved.text
    assert "Not reviewed" in saved.text
    assert "no-credential shortlist" in saved.text
    assert "Prepare application" in saved.text
    assert csv_response.status_code == 200
    assert "Senior Machine Learning Engineer" in csv_response.text
    assert "Not reviewed" in csv_response.text

    packet = client.post(
        f"/jobs/{job_id}/application-packet",
        data={"target_profile_id": target_profile_id},
        follow_redirects=False,
    )
    saved_after_packet = client.get(
        f"/dashboard/saved?target_profile_id={target_profile_id}"
    )

    assert packet.status_code == 303
    assert "Prepared" in saved_after_packet.text
    assert "Manual submit" in saved_after_packet.text


def test_dashboard_refresh_sources_requires_target_profile_id():
    app = create_app()
    client = TestClient(app)

    response = client.post("/dashboard/refresh-sources", data={})

    assert response.status_code == 400
    assert "target_profile_id is required" in response.text


def test_dashboard_profile_summary_offers_preference_edit_form():
    app = create_app()
    target_profile_id = _seed_reviewable_job(app.state.conn)
    client = TestClient(app)

    response = client.get(f"/dashboard?target_profile_id={target_profile_id}")

    assert response.status_code == 200
    assert f'action="/preferences/{target_profile_id}"' in response.text
    assert 'name="role"' in response.text
    assert 'value="Machine Learning Engineer"' in response.text
    assert 'name="location"' in response.text
    assert 'value="New York"' in response.text
    assert "Update target" in response.text


def test_update_preferences_bumps_version_and_hides_old_reviews():
    app = create_app()
    target_profile_id = _seed_reviewed_match(app.state.conn)
    client = TestClient(app)

    response = client.post(
        f"/preferences/{target_profile_id}",
        data={
            "role": "Data Scientist",
            "level": "senior",
            "location": "San Francisco",
            "work_mode": "hybrid",
            "company_stage": "growth",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == (
        f"/dashboard?target_profile_id={target_profile_id}&preferences_status=updated"
    )
    row = app.state.conn.execute(
        """
        SELECT version, desired_titles_json, locations_json, remote_modes_json
        FROM target_profiles
        WHERE id = ?
        """,
        (target_profile_id,),
    ).fetchone()
    assert row["version"] == 2
    assert "Data Scientist" in row["desired_titles_json"]
    assert "San Francisco" in row["locations_json"]
    assert "hybrid" in row["remote_modes_json"]

    dashboard = client.get(response.headers["location"])
    assert "Strong fit" not in dashboard.text
    assert "Prioritize" not in dashboard.text
    assert "Jobs waiting for fit review" in dashboard.text
    assert "Senior Machine Learning Engineer" in dashboard.text
    assert "Version 2" in dashboard.text


def test_dashboard_fit_review_provider_failure_returns_safe_error():
    app = create_app()
    target_profile_id = _seed_reviewable_job(app.state.conn)
    app.state.fit_gate_client = FailingFitGateClient()
    client = TestClient(app, raise_server_exceptions=False)

    response = client.post(
        "/dashboard/review-jobs",
        data={"target_profile_id": target_profile_id, "llm_consent": "on"},
    )

    assert response.status_code == 502
    assert "Fit review failed" in response.text
    assert "provider timeout" not in response.text
    assert "fit_gate:" not in response.text
    request = app.state.conn.execute(
        "SELECT feature, status, error FROM llm_requests"
    ).fetchone()
    assert dict(request) == {
        "feature": "fit_gate",
        "status": "failed",
        "error": "provider timeout",
    }


def _seed_profile_and_source(conn):
    target_profile_id = _seed_profile(conn)
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
    conn.commit()
    return target_profile_id


def _seed_reviewable_job(conn):
    target_profile_id = _seed_profile(conn)
    company_id = conn.execute(
        """
        INSERT INTO companies (name, normalized_name, stage)
        VALUES (?, ?, ?)
        """,
        ("Example AI", "example ai", "growth"),
    ).lastrowid
    conn.execute(
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
            "dashboard-route-job",
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
            "dashboard-route-hash",
        ),
    )
    conn.commit()
    return target_profile_id


def _seed_reviewed_match(conn):
    target_profile_id = _seed_reviewable_job(conn)
    job_id = conn.execute("SELECT id FROM jobs LIMIT 1").fetchone()["id"]
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
            93,
            "Strong fit",
            '["Role and skills fit"]',
            "[]",
            "Prioritize",
            1,
        ),
    )
    conn.commit()
    return target_profile_id


def _seed_profile(conn):
    resume_asset_id = conn.execute(
        """
        INSERT INTO resume_assets (original_filename, content_type, storage_path, sha256)
        VALUES (?, ?, ?, ?)
        """,
        ("resume.pdf", "application/pdf", "/tmp/resume.pdf", "dashboard-route-sha"),
    ).lastrowid
    target_profile_id = create_target_profile(
        conn,
        resume_asset_id=resume_asset_id,
        keywords=KEYWORDS,
        preferences=PREFERENCES,
    )
    return target_profile_id


def _raw_job(title="Senior Machine Learning Engineer"):
    return RawJob(
        external_id=title.casefold().replace(" ", "-"),
        title=title,
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
