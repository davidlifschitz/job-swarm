from fastapi.testclient import TestClient

from ml_job_swarm.app import create_app
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


def _seed_profile_and_job(app):
    conn = app.state.conn
    resume_asset_id = conn.execute(
        """
        INSERT INTO resume_assets (original_filename, content_type, storage_path, sha256)
        VALUES (?, ?, ?, ?)
        """,
        ("resume.pdf", "application/pdf", "/tmp/resume.pdf", "api-v1-sha"),
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
        ("Dataiku", "dataiku", "growth"),
    ).lastrowid
    job_id = conn.execute(
        """
        INSERT INTO jobs (
          company_id, external_id, title, source_url, content_hash, status
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            company_id,
            "dataiku-role",
            "Senior ML Engineer",
            "https://boards.greenhouse.io/dataiku/jobs/1",
            "api-v1-job",
            "open",
        ),
    ).lastrowid
    conn.execute(
        """
        INSERT INTO fit_reviews (
          job_id, target_profile_id, fit_score, label,
          reasons_json, risks_json, recommendation, profile_version
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            job_id,
            target_profile_id,
            90,
            "Strong fit",
            '["Role fit"]',
            "[]",
            "Prioritize",
            1,
        ),
    )
    conn.commit()
    return target_profile_id, int(job_id)


def test_api_v1_health_and_profiles():
    app = create_app()
    client = TestClient(app)

    health = client.get("/api/v1/health")
    assert health.status_code == 200
    payload = health.json()
    assert payload["status"] == "ok"
    assert payload["profile_count"] == 0
    assert payload["job_count"] == 0
    assert "db_path" in payload

    profiles = client.get("/api/v1/profiles")
    assert profiles.status_code == 200
    assert profiles.json()["profiles"] == []


def test_api_v1_dashboard_and_connections_import():
    app = create_app()
    target_profile_id, _job_id = _seed_profile_and_job(app)
    client = TestClient(app)

    dashboard = client.get(
        f"/api/v1/dashboard?target_profile_id={target_profile_id}&connection_filter=with_connections"
    )
    assert dashboard.status_code == 200
    payload = dashboard.json()
    assert payload["target_profile_id"] == target_profile_id
    assert payload["companies"] == []
    assert "resume_sections" in payload
    assert "unreviewed_jobs" in payload
    assert "rules_preview_companies" in payload
    assert "referral_network" in payload

    csv_bytes = (
        "First Name,Last Name,URL,Email Address,Company,Position,Connected On\n"
        "Jamie,Example,https://www.linkedin.com/in/jamie-example-fixture,,Dataiku,TA Partner,12 Jun 2026\n"
    ).encode()
    imported = client.post(
        "/api/v1/connections/import",
        files={"connections_file": ("Connections.csv", csv_bytes, "text/csv")},
    )
    assert imported.status_code == 200
    assert imported.json()["imported"] == 1

    dashboard_with_connections = client.get(
        f"/api/v1/dashboard?target_profile_id={target_profile_id}&connection_filter=with_connections"
    )
    assert dashboard_with_connections.status_code == 200
    companies = dashboard_with_connections.json()["companies"]
    assert len(companies) == 1
    assert companies[0]["name"] == "Dataiku"
    assert companies[0]["connection_count"] == 1


def test_api_v1_onboarding_preferences_and_saved_jobs():
    app = create_app()
    conn = app.state.conn
    resume_asset_id = conn.execute(
        """
        INSERT INTO resume_assets (original_filename, content_type, storage_path, sha256)
        VALUES (?, ?, ?, ?)
        """,
        ("resume.pdf", "application/pdf", "/tmp/resume.pdf", "onboarding-sha"),
    ).lastrowid
    conn.commit()
    client = TestClient(app)

    onboarding = client.get("/api/v1/onboarding")
    assert onboarding.status_code == 200
    assert onboarding.json()["has_profiles"] is False

    created = client.post(
        "/api/v1/onboarding/preferences",
        json={
            "resume_asset_id": resume_asset_id,
            "role": "Machine Learning Engineer",
            "level": "senior",
            "location": "New York",
            "work_mode": "remote",
            "company_stage": "growth",
        },
    )
    assert created.status_code == 200
    target_profile_id = created.json()["target_profile_id"]

    saved = client.get(f"/api/v1/saved-jobs?target_profile_id={target_profile_id}")
    assert saved.status_code == 200
    assert saved.json()["saved_jobs"] == []

    admin = client.get("/api/v1/admin/sources")
    assert admin.status_code == 200
    assert "sources" in admin.json()
    assert "support_summary" in admin.json()


def test_api_v1_onboarding_resume_accepts_pdf_by_suffix():
    app = create_app()
    client = TestClient(app)
    pdf_bytes = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
    uploaded = client.post(
        "/api/v1/onboarding/resume",
        files={"resume": ("resume.pdf", pdf_bytes, "application/octet-stream")},
    )
    assert uploaded.status_code == 200
    payload = uploaded.json()
    assert payload["status"] == "ok"
    assert payload["resume_asset_id"] > 0


def test_api_v1_refresh_sources_accepts_query_param():
    app = create_app()
    target_profile_id, _job_id = _seed_profile_and_job(app)
    client = TestClient(app)

    response = client.post(
        f"/api/v1/dashboard/refresh-sources?target_profile_id={target_profile_id}"
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_api_v1_job_detail_and_decision():
    app = create_app()
    target_profile_id, job_id = _seed_profile_and_job(app)
    client = TestClient(app)

    detail = client.get(
        f"/api/v1/jobs/{job_id}?target_profile_id={target_profile_id}"
    )
    assert detail.status_code == 200
    payload = detail.json()
    assert payload["job"]["title"] == "Senior ML Engineer"
    assert payload["application_packet"] is None
    assert "referral_contacts" in payload

    decision = client.post(
        f"/api/v1/jobs/{job_id}/decision",
        json={
            "target_profile_id": target_profile_id,
            "decision": "saved",
            "notes": "Strong referral path",
        },
    )
    assert decision.status_code == 200

    saved = client.get(f"/api/v1/saved-jobs?target_profile_id={target_profile_id}")
    assert saved.status_code == 200
    assert len(saved.json()["saved_jobs"]) == 1
    assert saved.json()["saved_jobs"][0]["notes"] == "Strong referral path"