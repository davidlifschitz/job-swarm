import csv
import io
import json

from fastapi.testclient import TestClient

from ml_job_swarm import resume_extract
from ml_job_swarm.resume_assets import load_resume_asset_bytes
from ml_job_swarm.app import create_app
from ml_job_swarm.decisions import record_job_decision
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


def test_onboarding_page_loads():
    client = TestClient(create_app())

    response = client.get("/onboarding")

    assert response.status_code == 200
    assert "Upload resume" in response.text
    assert "name=\"resume\"" in response.text


def test_onboarding_renders_wizard_with_upload_step_active():
    client = TestClient(create_app())

    response = client.get("/onboarding")

    assert response.status_code == 200
    assert 'class="wizard-steps"' in response.text
    assert 'data-step-id="upload"' in response.text
    assert 'data-step-id="preferences"' in response.text
    assert 'data-step-id="matches"' in response.text
    assert 'data-step-id="upload" aria-current="step"' in response.text
    assert 'data-step-id="preferences" aria-current="step"' not in response.text


def test_onboarding_with_resume_marks_preferences_step_active():
    client = TestClient(create_app())

    response = client.get("/onboarding?resume_asset_id=42")

    assert response.status_code == 200
    assert 'class="wizard-steps"' in response.text
    assert 'data-step-id="preferences" aria-current="step"' in response.text
    assert 'data-step-id="upload" aria-current="step"' not in response.text


def test_onboarding_page_renders_global_nav_with_active_link():
    client = TestClient(create_app())

    response = client.get("/onboarding")

    assert response.status_code == 200
    assert 'class="global-nav"' in response.text
    assert 'href="/onboarding"' in response.text
    assert 'href="/dashboard"' in response.text
    assert 'href="/admin/sources"' in response.text
    assert 'href="/onboarding" aria-current="page"' in response.text


def test_dashboard_empty_state_links_to_onboarding():
    client = TestClient(create_app())

    response = client.get("/dashboard")

    assert response.status_code == 200
    assert 'href="/onboarding"' in response.text
    assert 'class="empty"' in response.text
    assert ">Complete preferences before matching" in response.text


def test_dashboard_renders_global_nav_with_active_link():
    client = TestClient(create_app())

    response = client.get("/dashboard")

    assert response.status_code == 200
    assert 'class="global-nav"' in response.text
    assert 'href="/dashboard" aria-current="page"' in response.text


def test_resume_upload_requires_supported_type():
    client = TestClient(create_app())

    response = client.post(
        "/resume",
        files={"resume": ("notes.txt", b"plain text", "text/plain")},
    )

    assert response.status_code == 400
    assert "PDF or DOCX" in response.text


def test_resume_upload_parses_pdf_into_sections_and_keywords(monkeypatch):
    app = create_app()
    client = TestClient(app)
    monkeypatch.setattr(
        resume_extract,
        "_extract_pdf_text",
        lambda path: """
        SUMMARY
        Machine learning engineer building production systems.

        SKILLS
        Python, PyTorch, SQL

        EXPERIENCE
        Built retrieval and ranking systems.

        EDUCATION
        BS Computer Science
        """,
    )

    response = client.post(
        "/resume",
        files={"resume": ("resume.pdf", b"%PDF fake", "application/pdf")},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"].startswith("/onboarding?resume_asset_id=")
    parse_run = app.state.conn.execute(
        """
        SELECT status, confidence, vision_fallback_status
        FROM resume_parse_runs
        """
    ).fetchone()
    assert parse_run["status"] == "parsed"
    assert parse_run["confidence"] >= 0.8
    assert parse_run["vision_fallback_status"] == "not_needed"
    sections = app.state.conn.execute(
        "SELECT section_type, text FROM resume_sections ORDER BY sort_order"
    ).fetchall()
    assert {row["section_type"] for row in sections} >= {
        "summary",
        "skills",
        "experience",
        "education",
    }
    keywords = {
        row["keyword"]
        for row in app.state.conn.execute("SELECT keyword FROM resume_keywords")
    }
    assert {"python", "pytorch", "sql"} <= keywords


def test_duplicate_resume_upload_reuses_asset_without_foreign_key_error(monkeypatch):
    app = create_app()
    client = TestClient(app)
    monkeypatch.setattr(
        resume_extract,
        "_extract_pdf_text",
        lambda path: """
        SUMMARY
        Machine learning engineer.

        SKILLS
        Python, PyTorch
        """,
    )

    first = client.post(
        "/resume",
        files={"resume": ("resume.pdf", b"%PDF same", "application/pdf")},
        follow_redirects=False,
    )
    second = client.post(
        "/resume",
        files={"resume": ("resume.pdf", b"%PDF same", "application/pdf")},
        follow_redirects=False,
    )

    assert first.status_code == 303
    assert second.status_code == 303
    assert first.headers["location"] == second.headers["location"]
    assert app.state.conn.execute("SELECT COUNT(*) FROM resume_assets").fetchone()[0] == 1
    assert (
        app.state.conn.execute("SELECT COUNT(*) FROM resume_parse_runs").fetchone()[0]
        == 2
    )


def test_low_confidence_resume_upload_records_pending_vision_consent(monkeypatch):
    app = create_app()
    client = TestClient(app)
    monkeypatch.setattr(resume_extract, "_extract_pdf_text", lambda path: "scanned")

    response = client.post(
        "/resume",
        files={"resume": ("resume.pdf", b"%PDF fake", "application/pdf")},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert "vision_fallback=needed" in response.headers["location"]
    row = app.state.conn.execute(
        """
        SELECT status, vision_fallback_status, vision_fallback_consented_at
        FROM resume_parse_runs
        """
    ).fetchone()
    assert dict(row) == {
        "status": "needs_vision_fallback",
        "vision_fallback_status": "pending_consent",
        "vision_fallback_consented_at": None,
    }


def test_onboarding_shows_vision_fallback_consent_prompt():
    client = TestClient(create_app())

    response = client.get("/onboarding?resume_asset_id=7&vision_fallback=needed")

    assert response.status_code == 200
    assert "Vision fallback" in response.text
    assert 'action="/resume/vision-fallback"' in response.text
    assert 'name="resume_asset_id" value="7"' in response.text


def test_onboarding_panel_offers_skip_vision_fallback():
    client = TestClient(create_app())

    response = client.get("/onboarding?resume_asset_id=7&vision_fallback=needed")

    assert response.status_code == 200
    assert 'action="/resume/decline-vision-fallback"' in response.text
    assert "Skip and use what we parsed" in response.text


def test_decline_vision_fallback_marks_declined_and_redirects(monkeypatch):
    app = create_app()
    client = TestClient(app)
    monkeypatch.setattr(resume_extract, "_extract_pdf_text", lambda path: "scanned")
    upload_response = client.post(
        "/resume",
        files={"resume": ("resume.pdf", b"%PDF fake", "application/pdf")},
        follow_redirects=False,
    )
    assert upload_response.status_code == 303

    response = client.post(
        "/resume/decline-vision-fallback",
        data={"resume_asset_id": 1},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/onboarding?resume_asset_id=1"
    row = app.state.conn.execute(
        "SELECT vision_fallback_status FROM resume_parse_runs"
    ).fetchone()
    assert row["vision_fallback_status"] == "declined"


def test_decline_vision_fallback_requires_pending_parse_run():
    client = TestClient(create_app())

    response = client.post(
        "/resume/decline-vision-fallback",
        data={"resume_asset_id": 999},
    )

    assert response.status_code == 400
    assert "No pending vision fallback" in response.text


def test_vision_fallback_requires_configured_provider(monkeypatch):
    app = create_app()
    client = TestClient(app)
    monkeypatch.setattr(resume_extract, "_extract_pdf_text", lambda path: "scanned")
    upload_response = client.post(
        "/resume",
        files={"resume": ("resume.pdf", b"%PDF fake", "application/pdf")},
        follow_redirects=False,
    )
    assert upload_response.status_code == 303

    response = client.post(
        "/resume/vision-fallback",
        data={"resume_asset_id": 1},
    )

    assert response.status_code == 503
    assert "Vision fallback provider is not configured" in response.text
    row = app.state.conn.execute(
        "SELECT vision_fallback_status FROM resume_parse_runs"
    ).fetchone()
    assert row["vision_fallback_status"] == "pending_consent"


def test_vision_fallback_consent_records_llm_metadata_and_sections(
    monkeypatch, tmp_path
):
    class FakeVisionProvider:
        provider = "openrouter"
        model = "openrouter/test-vision"

        def __init__(self):
            self.requests = []

        def complete(self, request):
            self.requests.append(request)
            assert request.feature == "resume_vision_fallback"
            assert request.input_reference == "resume_asset:1"
            assert "PRIVATE VISION RESUME TEXT" not in request.private_prompt
            assert request.private_content_parts
            assert request.private_content_parts[0]["type"] == "image_url"
            assert request.private_content_parts[0]["image_url"]["url"].startswith(
                "data:image/png;base64,"
            )
            return {
                "extracted_text": """
                SUMMARY
                Machine learning engineer.

                SKILLS
                Python, PyTorch, SQL

                EXPERIENCE
                Built model evaluation systems.
                """,
                "confidence": 0.93,
                "warnings": [],
            }

    app = create_app()
    app.state.resume_asset_dir = tmp_path
    provider = FakeVisionProvider()
    app.state.vision_fallback_provider = provider
    client = TestClient(app)
    monkeypatch.setattr(resume_extract, "_extract_pdf_text", lambda path: "scanned")
    monkeypatch.setattr(
        "ml_job_swarm.resume_assets._render_pdf_pages_as_png",
        lambda content, max_pages: [b"png-page"],
    )
    upload_response = client.post(
        "/resume",
        files={"resume": ("resume.pdf", b"%PDF fake", "application/pdf")},
        follow_redirects=False,
    )
    assert upload_response.status_code == 303

    response = client.post(
        "/resume/vision-fallback",
        data={"resume_asset_id": 1},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/onboarding?resume_asset_id=1"
    runs = app.state.conn.execute(
        """
        SELECT status, vision_fallback_status, vision_fallback_consented_at
        FROM resume_parse_runs
        ORDER BY id
        """
    ).fetchall()
    assert runs[0]["status"] == "needs_vision_fallback"
    assert runs[0]["vision_fallback_status"] == "consented"
    assert runs[0]["vision_fallback_consented_at"] is not None
    assert runs[1]["status"] == "parsed"
    assert len(provider.requests) == 1
    persisted = app.state.conn.execute(
        "SELECT response_json FROM llm_requests WHERE feature = ?",
        ("resume_vision_fallback",),
    ).fetchone()["response_json"]
    assert "Machine learning engineer." not in persisted
    assert "resume_asset:1" in persisted
    keywords = {
        row["keyword"]
        for row in app.state.conn.execute("SELECT keyword FROM resume_keywords")
    }
    assert {"python", "pytorch", "sql"} <= keywords


def test_resume_upload_persists_resume_asset_file(monkeypatch, tmp_path):
    app = create_app()
    app.state.resume_asset_dir = tmp_path
    client = TestClient(app)
    monkeypatch.setattr(
        resume_extract,
        "_extract_pdf_text",
        lambda path: "SUMMARY\nMachine learning engineer\nSKILLS\nPython",
    )

    response = client.post(
        "/resume",
        files={"resume": ("resume.pdf", b"%PDF private bytes", "application/pdf")},
        follow_redirects=False,
    )

    assert response.status_code == 303
    row = app.state.conn.execute(
        "SELECT storage_path FROM resume_assets WHERE id = 1"
    ).fetchone()
    assert row["storage_path"].startswith("local://resume-assets/")
    assert load_resume_asset_bytes(row["storage_path"], tmp_path) == b"%PDF private bytes"


def test_vision_fallback_missing_asset_preserves_pending_status(monkeypatch, tmp_path):
    class FakeVisionProvider:
        provider = "openrouter"
        model = "openrouter/test-vision"
        requests = []

        def complete(self, request):
            self.requests.append(request)
            return {}

    app = create_app()
    app.state.resume_asset_dir = tmp_path
    provider = FakeVisionProvider()
    app.state.vision_fallback_provider = provider
    client = TestClient(app)
    monkeypatch.setattr(resume_extract, "_extract_pdf_text", lambda path: "scanned")
    upload_response = client.post(
        "/resume",
        files={"resume": ("resume.pdf", b"%PDF private bytes", "application/pdf")},
        follow_redirects=False,
    )
    assert upload_response.status_code == 303
    row = app.state.conn.execute(
        "SELECT storage_path FROM resume_assets WHERE id = 1"
    ).fetchone()
    asset_name = row["storage_path"].removeprefix("local://resume-assets/")
    (tmp_path / asset_name).unlink()

    response = client.post(
        "/resume/vision-fallback",
        data={"resume_asset_id": 1},
        follow_redirects=False,
    )

    assert response.status_code == 502
    assert "Stored resume asset is unavailable" in response.text
    assert provider.requests == []
    status = app.state.conn.execute(
        "SELECT vision_fallback_status FROM resume_parse_runs"
    ).fetchone()["vision_fallback_status"]
    assert status == "pending_consent"


def test_preferences_missing_disables_matching():
    client = TestClient(create_app())

    response = client.post(
        "/preferences",
        data={"role": "Machine Learning Engineer", "level": "senior"},
    )

    assert response.status_code == 400
    assert 'action="/preferences"' in response.text
    assert "field-error" in response.text
    dashboard = client.get("/dashboard")
    assert "Complete preferences before matching" in dashboard.text


def test_preferences_missing_rerenders_form_with_inline_errors():
    client = TestClient(create_app())

    response = client.post(
        "/preferences",
        data={"role": "Machine Learning Engineer", "level": "senior"},
    )

    assert response.status_code == 400
    assert 'action="/preferences"' in response.text
    assert 'value="Machine Learning Engineer"' in response.text
    assert 'value="senior"' in response.text
    assert 'class="field-error"' in response.text
    assert "Location is required" in response.text
    assert "Work mode is required" in response.text
    assert "Company stage is required" in response.text
    assert "Role is required" not in response.text
    assert "Level is required" not in response.text


def test_preferences_missing_resume_asset_rerenders_form():
    client = TestClient(create_app())

    response = client.post(
        "/preferences",
        data={
            "role": "Machine Learning Engineer",
            "level": "senior",
            "location": "New York",
            "work_mode": "remote",
            "company_stage": "growth",
        },
    )

    assert response.status_code == 400
    assert 'action="/preferences"' in response.text
    assert "Upload a resume" in response.text


def test_dashboard_exposes_fit_review_action():
    app = create_app()
    profile_id = _seed_unreviewed_job(
        app.state.conn,
        company_name="Example AI",
        job_title="Unreviewed ML Engineer",
    )
    client = TestClient(app)

    response = client.get(f"/dashboard?target_profile_id={profile_id}")

    assert response.status_code == 200
    assert 'action="/dashboard/review-jobs"' in response.text
    assert 'name="target_profile_id"' in response.text
    assert 'name="llm_consent"' in response.text
    assert "Run fit review" in response.text


def test_dashboard_review_jobs_requires_llm_consent():
    app = create_app()
    profile_id = _seed_unreviewed_job(
        app.state.conn,
        company_name="Example AI",
        job_title="Unreviewed ML Engineer",
    )
    app.state.fit_gate_client = FakeFitGateClient()
    client = TestClient(app)

    response = client.post(
        "/dashboard/review-jobs",
        data={"target_profile_id": str(profile_id)},
    )

    assert response.status_code == 400
    assert "LLM consent is required" in response.text
    assert app.state.conn.execute("SELECT COUNT(*) FROM fit_reviews").fetchone()[0] == 0


def test_dashboard_review_jobs_requires_fit_gate_client():
    app = create_app()
    profile_id = _seed_unreviewed_job(
        app.state.conn,
        company_name="Example AI",
        job_title="Unreviewed ML Engineer",
    )
    client = TestClient(app)

    response = client.post(
        "/dashboard/review-jobs",
        data={"target_profile_id": str(profile_id), "llm_consent": "on"},
    )

    assert response.status_code == 503
    assert "Fit review client unavailable" in response.text
    assert app.state.conn.execute("SELECT COUNT(*) FROM fit_reviews").fetchone()[0] == 0


def test_dashboard_review_jobs_runs_fit_review_pipeline():
    app = create_app()
    profile_id = _seed_unreviewed_job(
        app.state.conn,
        company_name="Example AI",
        job_title="Unreviewed ML Engineer",
    )
    fit_client = FakeFitGateClient()
    app.state.fit_gate_client = fit_client
    client = TestClient(app)

    response = client.post(
        "/dashboard/review-jobs",
        data={"target_profile_id": str(profile_id), "llm_consent": "on"},
        follow_redirects=False,
    )
    dashboard = client.get(f"/dashboard?target_profile_id={profile_id}")

    review = app.state.conn.execute(
        """
        SELECT fit_score, label, recommendation
        FROM fit_reviews
        """
    ).fetchone()
    llm_request = app.state.conn.execute(
        "SELECT feature, status, response_json FROM llm_requests"
    ).fetchone()
    assert response.status_code == 303
    assert response.headers["location"] == f"/dashboard?target_profile_id={profile_id}"
    assert dict(review) == {
        "fit_score": 91,
        "label": "Strong fit",
        "recommendation": "Prioritize",
    }
    assert llm_request["feature"] == "fit_gate"
    assert llm_request["status"] == "succeeded"
    assert (
        json.loads(llm_request["response_json"])["input_reference"]
        == f"job:1|profile:{profile_id}|v:1"
    )
    assert len(fit_client.calls) == 1
    assert "Unreviewed ML Engineer" in dashboard.text
    assert "Strong fit" in dashboard.text


def test_dashboard_groups_jobs_by_company():
    app = create_app()
    profile_id = _seed_reviewed_job(
        app.state.conn,
        company_name="Example AI",
        job_title="Senior Machine Learning Engineer",
        label="Strong fit",
    )
    _seed_reviewed_job(
        app.state.conn,
        company_name="Example AI",
        job_title="AI Platform Engineer",
        label="Possible fit",
        target_profile_id=profile_id,
    )
    client = TestClient(app)

    response = client.get(f"/dashboard?target_profile_id={profile_id}")

    assert response.status_code == 200
    assert "Example AI" in response.text
    assert "Senior Machine Learning Engineer" in response.text
    assert "AI Platform Engineer" in response.text


def test_mismatch_risks_are_collapsed_data_not_main_rows():
    app = create_app()
    profile_id = _seed_reviewed_job(
        app.state.conn,
        company_name="Example AI",
        job_title="Visible ML Engineer",
        label="Strong fit",
    )
    _seed_reviewed_job(
        app.state.conn,
        company_name="Example AI",
        job_title="Risky Senior Role",
        label="Mismatch risk",
        target_profile_id=profile_id,
    )
    client = TestClient(app)

    response = client.get(f"/dashboard?target_profile_id={profile_id}")

    assert '<details class="mismatch-risks">' in response.text
    assert "Visible ML Engineer" in response.text
    assert "Risky Senior Role" in response.text
    assert (
        '<tr class="job-row" data-job-decision=""><td>Risky Senior Role</td>'
        not in response.text
    )


def test_dashboard_can_save_job_decision():
    app = create_app()
    profile_id = _seed_reviewed_job(
        app.state.conn,
        company_name="Example AI",
        job_title="Senior Machine Learning Engineer",
        label="Strong fit",
    )
    job_id = _job_id_for_title(app.state.conn, "Senior Machine Learning Engineer")
    client = TestClient(app)

    response = client.post(
        f"/jobs/{job_id}/decision",
        data={
            "target_profile_id": str(profile_id),
            "decision": "saved",
            "notes": "ask about infra team",
        },
        follow_redirects=False,
    )
    dashboard = client.get(f"/dashboard?target_profile_id={profile_id}")

    assert response.status_code == 303
    assert response.headers["location"] == (
        f"/dashboard?target_profile_id={profile_id}&decision_status=saved"
    )
    assert 'data-job-decision="saved"' in dashboard.text
    assert "Saved" in dashboard.text
    assert "ask about infra team" in dashboard.text


def test_dashboard_can_hide_and_restore_job_decision():
    app = create_app()
    profile_id = _seed_reviewed_job(
        app.state.conn,
        company_name="Example AI",
        job_title="Noisy ML Engineer",
        label="Strong fit",
    )
    job_id = _job_id_for_title(app.state.conn, "Noisy ML Engineer")
    client = TestClient(app)

    hide_response = client.post(
        f"/jobs/{job_id}/decision",
        data={
            "target_profile_id": str(profile_id),
            "decision": "hidden",
            "notes": "not the right team",
        },
        follow_redirects=False,
    )
    hidden_dashboard = client.get(f"/dashboard?target_profile_id={profile_id}")
    clear_response = client.post(
        f"/jobs/{job_id}/decision",
        data={"target_profile_id": str(profile_id), "decision": "clear"},
        follow_redirects=False,
    )
    restored_dashboard = client.get(f"/dashboard?target_profile_id={profile_id}")

    assert hide_response.status_code == 303
    assert '<details class="hidden-jobs">' in hidden_dashboard.text
    assert "Hidden by you" in hidden_dashboard.text
    assert "Noisy ML Engineer" in hidden_dashboard.text
    assert "not the right team" in hidden_dashboard.text
    assert '<tr class="job-row" data-job-decision="hidden">' not in hidden_dashboard.text
    assert clear_response.status_code == 303
    assert '<tr class="job-row" data-job-decision="">' in restored_dashboard.text


def test_dashboard_filters_saved_jobs_by_decision():
    app = create_app()
    profile_id = _seed_reviewed_job(
        app.state.conn,
        company_name="Example AI",
        job_title="Saved ML Engineer",
        label="Strong fit",
    )
    _seed_reviewed_job(
        app.state.conn,
        company_name="Example AI",
        job_title="Unmarked ML Engineer",
        label="Strong fit",
        target_profile_id=profile_id,
    )
    _seed_reviewed_job(
        app.state.conn,
        company_name="Example AI",
        job_title="Hidden ML Engineer",
        label="Strong fit",
        target_profile_id=profile_id,
    )
    saved_job_id = _job_id_for_title(app.state.conn, "Saved ML Engineer")
    hidden_job_id = _job_id_for_title(app.state.conn, "Hidden ML Engineer")
    record_job_decision(
        app.state.conn,
        job_id=saved_job_id,
        target_profile_id=profile_id,
        decision="saved",
    )
    record_job_decision(
        app.state.conn,
        job_id=hidden_job_id,
        target_profile_id=profile_id,
        decision="hidden",
    )
    client = TestClient(app)

    response = client.get(
        f"/dashboard?target_profile_id={profile_id}&decision_filter=saved"
    )

    assert response.status_code == 200
    assert 'aria-current="page">Saved' in response.text
    assert "Saved ML Engineer" in response.text
    assert "Unmarked ML Engineer" not in response.text
    assert "Hidden ML Engineer" not in response.text


def test_dashboard_filters_hidden_jobs_by_decision():
    app = create_app()
    profile_id = _seed_reviewed_job(
        app.state.conn,
        company_name="Example AI",
        job_title="Saved ML Engineer",
        label="Strong fit",
    )
    _seed_reviewed_job(
        app.state.conn,
        company_name="Example AI",
        job_title="Hidden ML Engineer",
        label="Strong fit",
        target_profile_id=profile_id,
    )
    saved_job_id = _job_id_for_title(app.state.conn, "Saved ML Engineer")
    hidden_job_id = _job_id_for_title(app.state.conn, "Hidden ML Engineer")
    record_job_decision(
        app.state.conn,
        job_id=saved_job_id,
        target_profile_id=profile_id,
        decision="saved",
    )
    record_job_decision(
        app.state.conn,
        job_id=hidden_job_id,
        target_profile_id=profile_id,
        decision="hidden",
        notes="restore later",
    )
    client = TestClient(app)

    response = client.get(
        f"/dashboard?target_profile_id={profile_id}&decision_filter=hidden"
    )

    assert response.status_code == 200
    assert 'aria-current="page">Hidden' in response.text
    assert '<tr class="job-row" data-job-decision="hidden">' in response.text
    assert "Hidden ML Engineer" in response.text
    assert "restore later" in response.text
    assert ">Hidden<" in response.text
    assert "Saved ML Engineer" not in response.text


def test_dashboard_invalid_decision_filter_falls_back_to_all():
    app = create_app()
    profile_id = _seed_reviewed_job(
        app.state.conn,
        company_name="Example AI",
        job_title="Saved ML Engineer",
        label="Strong fit",
    )
    _seed_reviewed_job(
        app.state.conn,
        company_name="Example AI",
        job_title="Unmarked ML Engineer",
        label="Strong fit",
        target_profile_id=profile_id,
    )
    saved_job_id = _job_id_for_title(app.state.conn, "Saved ML Engineer")
    record_job_decision(
        app.state.conn,
        job_id=saved_job_id,
        target_profile_id=profile_id,
        decision="saved",
    )
    client = TestClient(app)

    response = client.get(
        f"/dashboard?target_profile_id={profile_id}&decision_filter=unexpected"
    )

    assert response.status_code == 200
    assert 'aria-current="page">All' in response.text
    assert "Saved ML Engineer" in response.text
    assert "Unmarked ML Engineer" in response.text


def test_dashboard_decision_forms_preserve_active_filter_return_path():
    app = create_app()
    profile_id = _seed_reviewed_job(
        app.state.conn,
        company_name="Example AI",
        job_title="Saved ML Engineer",
        label="Strong fit",
    )
    saved_job_id = _job_id_for_title(app.state.conn, "Saved ML Engineer")
    record_job_decision(
        app.state.conn,
        job_id=saved_job_id,
        target_profile_id=profile_id,
        decision="saved",
    )
    client = TestClient(app)

    response = client.get(
        f"/dashboard?target_profile_id={profile_id}&decision_filter=saved"
    )

    expected_return_to = (
        f'name="return_to" '
        f'value="/dashboard?target_profile_id={profile_id}&amp;decision_filter=saved"'
    )
    assert response.status_code == 200
    assert expected_return_to in response.text


def test_dashboard_rejects_invalid_job_decision():
    app = create_app()
    profile_id = _seed_reviewed_job(
        app.state.conn,
        company_name="Example AI",
        job_title="Senior Machine Learning Engineer",
        label="Strong fit",
    )
    job_id = _job_id_for_title(app.state.conn, "Senior Machine Learning Engineer")
    client = TestClient(app)

    response = client.post(
        f"/jobs/{job_id}/decision",
        data={"target_profile_id": str(profile_id), "decision": "applied"},
    )

    assert response.status_code == 400
    assert "Invalid job decision" in response.text


def test_dashboard_exposes_saved_jobs_export_link():
    app = create_app()
    profile_id = _seed_reviewed_job(
        app.state.conn,
        company_name="Example AI",
        job_title="Senior Machine Learning Engineer",
        label="Strong fit",
    )
    client = TestClient(app)

    response = client.get(f"/dashboard?target_profile_id={profile_id}")

    assert response.status_code == 200
    assert f"/dashboard/saved.csv?target_profile_id={profile_id}" in response.text
    assert f"/dashboard/saved?target_profile_id={profile_id}" in response.text


def test_dashboard_shows_active_profile_summary_with_latest_keywords():
    app = create_app()
    profile_id = _seed_reviewed_job(
        app.state.conn,
        company_name="Example AI",
        job_title="Senior Machine Learning Engineer",
        label="Strong fit",
    )
    _seed_resume_keywords(app.state.conn, profile_id, ["oldkeyword"])
    _seed_resume_keywords(app.state.conn, profile_id, ["python", "pytorch", "sql"])
    client = TestClient(app)

    response = client.get(f"/dashboard?target_profile_id={profile_id}")

    assert response.status_code == 200
    assert "Profile summary" in response.text
    assert "Machine Learning Engineer" in response.text
    assert "Version 1" in response.text
    assert "resume.pdf" in response.text
    assert "senior" in response.text
    assert "New York" in response.text
    assert "remote" in response.text
    assert "growth" in response.text
    assert "python" in response.text
    assert "pytorch" in response.text
    assert "sql" in response.text
    assert "oldkeyword" not in response.text
    assert "PRIVATE RESUME TEXT" not in response.text


def test_dashboard_hides_profile_summary_when_onboarding_required():
    client = TestClient(create_app())

    response = client.get("/dashboard")

    assert response.status_code == 200
    assert "Complete preferences before matching" in response.text
    assert "Profile summary" not in response.text


def test_dashboard_profile_summary_handles_missing_keywords():
    app = create_app()
    profile_id = _seed_reviewed_job(
        app.state.conn,
        company_name="Example AI",
        job_title="Senior Machine Learning Engineer",
        label="Strong fit",
    )
    client = TestClient(app)

    response = client.get(f"/dashboard?target_profile_id={profile_id}")

    assert response.status_code == 200
    assert "Profile summary" in response.text
    assert "No resume keywords captured" in response.text


def test_dashboard_links_jobs_to_detail_page():
    app = create_app()
    profile_id = _seed_reviewed_job(
        app.state.conn,
        company_name="Example AI",
        job_title="Senior Machine Learning Engineer",
        label="Strong fit",
    )
    visible_job_id = _job_id_for_title(app.state.conn, "Senior Machine Learning Engineer")
    _seed_reviewed_job(
        app.state.conn,
        company_name="Example AI",
        job_title="Risky ML Engineer",
        label="Mismatch risk",
        target_profile_id=profile_id,
    )
    risky_job_id = _job_id_for_title(app.state.conn, "Risky ML Engineer")
    _seed_reviewed_job(
        app.state.conn,
        company_name="Example AI",
        job_title="Hidden ML Engineer",
        label="Strong fit",
        target_profile_id=profile_id,
    )
    hidden_job_id = _job_id_for_title(app.state.conn, "Hidden ML Engineer")
    record_job_decision(
        app.state.conn,
        job_id=hidden_job_id,
        target_profile_id=profile_id,
        decision="hidden",
    )
    client = TestClient(app)

    response = client.get(f"/dashboard?target_profile_id={profile_id}")

    assert response.status_code == 200
    assert f"/jobs/{visible_job_id}?target_profile_id={profile_id}" in response.text
    assert f"/jobs/{risky_job_id}?target_profile_id={profile_id}" in response.text
    assert f"/jobs/{hidden_job_id}?target_profile_id={profile_id}" in response.text


def test_job_detail_requires_target_profile():
    app = create_app()
    _seed_reviewed_job(
        app.state.conn,
        company_name="Example AI",
        job_title="Senior Machine Learning Engineer",
        label="Strong fit",
    )
    job_id = _job_id_for_title(app.state.conn, "Senior Machine Learning Engineer")
    client = TestClient(app)

    response = client.get(f"/jobs/{job_id}")

    assert response.status_code == 400
    assert "target_profile_id is required" in response.text


def test_job_detail_returns_not_found_for_missing_job():
    app = create_app()
    profile_id = _seed_reviewed_job(
        app.state.conn,
        company_name="Example AI",
        job_title="Senior Machine Learning Engineer",
        label="Strong fit",
    )
    client = TestClient(app)

    response = client.get(f"/jobs/999?target_profile_id={profile_id}")

    assert response.status_code == 404
    assert "Job not found" in response.text


def test_job_detail_renders_profile_scoped_fit_and_decision_controls():
    app = create_app()
    profile_id = _seed_reviewed_job(
        app.state.conn,
        company_name="Example AI",
        job_title="Senior Machine Learning Engineer",
        label="Strong fit",
    )
    job_id = _job_id_for_title(app.state.conn, "Senior Machine Learning Engineer")
    record_job_decision(
        app.state.conn,
        job_id=job_id,
        target_profile_id=profile_id,
        decision="saved",
        notes="ask hiring manager",
    )
    client = TestClient(app)

    response = client.get(f"/jobs/{job_id}?target_profile_id={profile_id}")

    assert response.status_code == 200
    assert "Senior Machine Learning Engineer" in response.text
    assert "Example AI" in response.text
    assert "Build ML ranking systems." in response.text
    assert "Python and PyTorch required." in response.text
    assert "90" in response.text
    assert "Strong fit" in response.text
    assert "matches role" in response.text
    assert "Review" in response.text
    assert "ask hiring manager" in response.text
    assert "https://jobs.example/apply" in response.text
    assert "https://boards.greenhouse.io/example/jobs/1" in response.text
    assert 'name="decision" value="saved"' in response.text
    assert 'name="decision" value="hidden"' in response.text
    assert 'name="decision" value="clear"' in response.text


def test_job_detail_renders_application_workspace_prepare_action():
    app = create_app()
    profile_id = _seed_reviewed_job(
        app.state.conn,
        company_name="Example AI",
        job_title="Senior Machine Learning Engineer",
        label="Strong fit",
    )
    job_id = _job_id_for_title(app.state.conn, "Senior Machine Learning Engineer")
    _seed_private_resume_section(app.state.conn, profile_id, "PRIVATE RESUME TEXT")
    client = TestClient(app)

    response = client.get(f"/jobs/{job_id}?target_profile_id={profile_id}")

    assert response.status_code == 200
    assert "Application workspace" in response.text
    assert f'action="/jobs/{job_id}/application-packet"' in response.text
    assert f'name="target_profile_id" value="{profile_id}"' in response.text
    assert "Prepare application packet" in response.text
    assert "manual final submit" in response.text
    assert "PRIVATE RESUME TEXT" not in response.text


def test_job_detail_renders_local_referral_workspace_empty_state():
    app = create_app()
    profile_id = _seed_reviewed_job(
        app.state.conn,
        company_name="Example AI",
        job_title="Senior Machine Learning Engineer",
        label="Strong fit",
    )
    job_id = _job_id_for_title(app.state.conn, "Senior Machine Learning Engineer")
    _seed_private_resume_section(app.state.conn, profile_id, "PRIVATE RESUME TEXT")
    client = TestClient(app)

    response = client.get(f"/jobs/{job_id}?target_profile_id={profile_id}")

    assert response.status_code == 200
    assert "Local referral contacts" in response.text
    assert f'action="/jobs/{job_id}/referral-contacts"' in response.text
    assert "No local referral contacts for this company yet." in response.text
    assert "PRIVATE RESUME TEXT" not in response.text


def test_adding_local_referral_contact_links_to_job_company():
    app = create_app()
    profile_id = _seed_reviewed_job(
        app.state.conn,
        company_name="Example AI",
        job_title="Senior Machine Learning Engineer",
        label="Strong fit",
    )
    job_id = _job_id_for_title(app.state.conn, "Senior Machine Learning Engineer")
    client = TestClient(app)

    response = client.post(
        f"/jobs/{job_id}/referral-contacts",
        data={
            "target_profile_id": str(profile_id),
            "name": "Dana Referral",
            "email": "dana@example.com",
            "title": "Staff ML Engineer",
            "relationship": "former coworker",
            "notes": "ask about team scope",
        },
        follow_redirects=False,
    )
    detail = client.get(f"/jobs/{job_id}?target_profile_id={profile_id}")

    contact = app.state.conn.execute("SELECT * FROM contacts").fetchone()
    link = app.state.conn.execute("SELECT * FROM referral_contacts").fetchone()
    persisted = json.dumps({"contact": dict(contact), "link": dict(link)}, sort_keys=True)
    assert response.status_code == 303
    assert response.headers["location"] == f"/jobs/{job_id}?target_profile_id={profile_id}"
    assert contact["name"] == "Dana Referral"
    assert contact["email"] == "dana@example.com"
    assert link["relationship"] == "former coworker"
    assert "Dana Referral" in detail.text
    assert "Staff ML Engineer" in detail.text
    assert "ask about team scope" in detail.text
    assert "mailto:dana@example.com" not in detail.text
    assert "cookie" not in persisted.casefold()


def test_job_detail_referral_contacts_are_company_scoped():
    app = create_app()
    profile_id = _seed_reviewed_job(
        app.state.conn,
        company_name="Example AI",
        job_title="Senior Machine Learning Engineer",
        label="Strong fit",
    )
    job_id = _job_id_for_title(app.state.conn, "Senior Machine Learning Engineer")
    other_company_id = app.state.conn.execute(
        "INSERT INTO companies (name, normalized_name) VALUES (?, ?)",
        ("Other AI", "other ai"),
    ).lastrowid
    other_contact_id = app.state.conn.execute(
        "INSERT INTO contacts (name, email, title, notes) VALUES (?, ?, ?, ?)",
        ("Other Contact", "other@example.com", "Director", "wrong company"),
    ).lastrowid
    app.state.conn.execute(
        """
        INSERT INTO referral_contacts (company_id, contact_id, relationship)
        VALUES (?, ?, ?)
        """,
        (other_company_id, other_contact_id, "friend"),
    )
    app.state.conn.commit()
    client = TestClient(app)
    client.post(
        f"/jobs/{job_id}/referral-contacts",
        data={
            "target_profile_id": str(profile_id),
            "name": "Dana Referral",
            "email": "dana@example.com",
            "title": "Staff ML Engineer",
            "relationship": "former coworker",
            "notes": "right company",
        },
    )

    response = client.get(f"/jobs/{job_id}?target_profile_id={profile_id}")

    assert "Dana Referral" in response.text
    assert "right company" in response.text
    assert "Other Contact" not in response.text
    assert "wrong company" not in response.text


def test_saved_jobs_page_shows_company_scoped_local_contacts_without_csv_export():
    app = create_app()
    profile_id = _seed_reviewed_job(
        app.state.conn,
        company_name="Example AI",
        job_title="Saved ML Engineer",
        label="Strong fit",
    )
    saved_job_id = _job_id_for_title(app.state.conn, "Saved ML Engineer")
    other_company_id = app.state.conn.execute(
        "INSERT INTO companies (name, normalized_name) VALUES (?, ?)",
        ("Other AI", "other ai"),
    ).lastrowid
    other_contact_id = app.state.conn.execute(
        "INSERT INTO contacts (name, email, title, notes) VALUES (?, ?, ?, ?)",
        ("Other Contact", "other@example.com", "Director", "wrong company"),
    ).lastrowid
    app.state.conn.execute(
        """
        INSERT INTO referral_contacts (company_id, contact_id, relationship)
        VALUES (?, ?, ?)
        """,
        (other_company_id, other_contact_id, "friend"),
    )
    app.state.conn.commit()
    record_job_decision(
        app.state.conn,
        job_id=saved_job_id,
        target_profile_id=profile_id,
        decision="saved",
    )
    client = TestClient(app)
    client.post(
        f"/jobs/{saved_job_id}/referral-contacts",
        data={
            "target_profile_id": str(profile_id),
            "name": "Dana Referral",
            "email": "dana@example.com",
            "title": "Staff ML Engineer",
            "relationship": "former coworker",
            "notes": "right company",
        },
    )

    page = client.get(f"/dashboard/saved?target_profile_id={profile_id}")
    csv_response = client.get(f"/dashboard/saved.csv?target_profile_id={profile_id}")

    assert "Dana Referral" in page.text
    assert "Staff ML Engineer" in page.text
    assert "Other Contact" not in page.text
    assert "dana@example.com" not in csv_response.text
    assert "Dana Referral" not in csv_response.text


def test_preparing_application_packet_creates_local_packet_and_redirects():
    app = create_app()
    profile_id = _seed_reviewed_job(
        app.state.conn,
        company_name="Example AI",
        job_title="Senior Machine Learning Engineer",
        label="Strong fit",
    )
    job_id = _job_id_for_title(app.state.conn, "Senior Machine Learning Engineer")
    _seed_private_resume_section(app.state.conn, profile_id, "PRIVATE RESUME TEXT")
    client = TestClient(app)

    response = client.post(
        f"/jobs/{job_id}/application-packet",
        data={"target_profile_id": str(profile_id)},
        follow_redirects=False,
    )
    second_response = client.post(
        f"/jobs/{job_id}/application-packet",
        data={"target_profile_id": str(profile_id)},
        follow_redirects=False,
    )

    rows = app.state.conn.execute("SELECT * FROM application_packets").fetchall()
    packet = json.loads(rows[0]["packet_json"])
    checklist = json.loads(rows[0]["checklist_json"])
    persisted = json.dumps([dict(row) for row in rows], sort_keys=True)
    assert response.status_code == 303
    assert response.headers["location"] == f"/jobs/{job_id}?target_profile_id={profile_id}"
    assert second_response.status_code == 303
    assert len(rows) == 1
    assert rows[0]["status"] == "prepared"
    assert rows[0]["manual_submit_url"] == "https://jobs.example/apply"
    assert packet["company"] == "Example AI"
    assert packet["title"] == "Senior Machine Learning Engineer"
    assert packet["fit_score"] == 90
    assert checklist[0]["label"] == "Review fit reasons and mismatch risks"
    assert "PRIVATE RESUME TEXT" not in persisted


def test_application_packet_includes_accepted_resume_rewrites_without_raw_resume():
    app = create_app()
    profile_id = _seed_reviewed_job(
        app.state.conn,
        company_name="Example AI",
        job_title="Senior Machine Learning Engineer",
        label="Strong fit",
    )
    job_id = _job_id_for_title(app.state.conn, "Senior Machine Learning Engineer")
    section_id = _seed_private_resume_section(
        app.state.conn,
        profile_id,
        "PRIVATE RESUME TEXT",
    )
    _seed_resume_rewrite_suggestion(
        app.state.conn,
        target_profile_id=profile_id,
        section_id=section_id,
        suggestion_text="Built ranking infrastructure for public launch.",
        status="accepted",
    )
    client = TestClient(app)

    response = client.post(
        f"/jobs/{job_id}/application-packet",
        data={"target_profile_id": str(profile_id)},
        follow_redirects=False,
    )
    packet_row = app.state.conn.execute("SELECT packet_json FROM application_packets").fetchone()
    packet = json.loads(packet_row["packet_json"])
    detail = client.get(f"/jobs/{job_id}?target_profile_id={profile_id}")

    assert response.status_code == 303
    assert packet["accepted_resume_rewrites"] == [
        {
            "section_id": section_id,
            "section_type": "experience",
            "heading": "Experience",
            "suggestion_text": "Built ranking infrastructure for public launch.",
        }
    ]
    persisted = json.dumps(packet, sort_keys=True) + detail.text
    assert "Accepted resume rewrites" in detail.text
    assert "Built ranking infrastructure for public launch." in detail.text
    assert "PRIVATE RESUME TEXT" not in persisted


def test_job_detail_renders_prepared_application_packet_summary():
    app = create_app()
    profile_id = _seed_reviewed_job(
        app.state.conn,
        company_name="Example AI",
        job_title="Senior Machine Learning Engineer",
        label="Strong fit",
    )
    job_id = _job_id_for_title(app.state.conn, "Senior Machine Learning Engineer")
    _seed_private_resume_section(app.state.conn, profile_id, "PRIVATE RESUME TEXT")
    client = TestClient(app)
    client.post(
        f"/jobs/{job_id}/application-packet",
        data={"target_profile_id": str(profile_id)},
    )

    response = client.get(f"/jobs/{job_id}?target_profile_id={profile_id}")

    assert response.status_code == 200
    assert "Packet summary" in response.text
    assert "Example AI" in response.text
    assert "Senior Machine Learning Engineer" in response.text
    assert "Strong fit" in response.text
    assert "90/100" in response.text
    assert "Review" in response.text
    assert "matches role" in response.text
    assert "Manual submit URL" in response.text
    assert "https://jobs.example/apply" in response.text
    assert "PRIVATE RESUME TEXT" not in response.text


def test_marking_application_packet_submitted_tracks_manual_status():
    app = create_app()
    profile_id = _seed_reviewed_job(
        app.state.conn,
        company_name="Example AI",
        job_title="Senior Machine Learning Engineer",
        label="Strong fit",
    )
    job_id = _job_id_for_title(app.state.conn, "Senior Machine Learning Engineer")
    client = TestClient(app)
    client.post(
        f"/jobs/{job_id}/application-packet",
        data={"target_profile_id": str(profile_id)},
    )
    packet_id = app.state.conn.execute(
        "SELECT id FROM application_packets"
    ).fetchone()["id"]

    response = client.post(
        f"/application-packets/{packet_id}/status",
        data={"target_profile_id": str(profile_id), "status": "submitted"},
        follow_redirects=False,
    )

    row = app.state.conn.execute(
        "SELECT status FROM application_packets WHERE id = ?",
        (packet_id,),
    ).fetchone()
    assert response.status_code == 303
    assert response.headers["location"] == f"/jobs/{job_id}?target_profile_id={profile_id}"
    assert row["status"] == "submitted"


def test_repreparing_submitted_application_packet_preserves_submitted_status():
    app = create_app()
    profile_id = _seed_reviewed_job(
        app.state.conn,
        company_name="Example AI",
        job_title="Submitted ML Engineer",
        label="Strong fit",
    )
    job_id = _job_id_for_title(app.state.conn, "Submitted ML Engineer")
    client = TestClient(app)
    client.post(
        f"/jobs/{job_id}/application-packet",
        data={"target_profile_id": str(profile_id)},
    )
    packet_id = app.state.conn.execute(
        "SELECT id FROM application_packets"
    ).fetchone()["id"]
    client.post(
        f"/application-packets/{packet_id}/status",
        data={"target_profile_id": str(profile_id), "status": "submitted"},
    )
    record_job_decision(
        app.state.conn,
        job_id=job_id,
        target_profile_id=profile_id,
        decision="saved",
    )

    response = client.post(
        f"/jobs/{job_id}/application-packet",
        data={"target_profile_id": str(profile_id)},
        follow_redirects=False,
    )

    row = app.state.conn.execute(
        "SELECT status FROM application_packets WHERE id = ?",
        (packet_id,),
    ).fetchone()
    assert response.status_code == 303
    assert row["status"] == "submitted"
    detail = client.get(f"/jobs/{job_id}?target_profile_id={profile_id}")
    saved = client.get(f"/dashboard/saved?target_profile_id={profile_id}")
    assert "Submitted packet preserved" in detail.text
    assert "Prepare application packet" not in detail.text
    assert "Submitted" in saved.text
    assert "Prepare application" not in saved.text


def test_saved_jobs_page_shows_application_packet_status():
    app = create_app()
    profile_id = _seed_reviewed_job(
        app.state.conn,
        company_name="Example AI",
        job_title="Prepared ML Engineer",
        label="Strong fit",
    )
    prepared_job_id = _job_id_for_title(app.state.conn, "Prepared ML Engineer")
    _seed_reviewed_job(
        app.state.conn,
        company_name="Example AI",
        job_title="Submitted ML Engineer",
        label="Strong fit",
        target_profile_id=profile_id,
    )
    submitted_job_id = _job_id_for_title(app.state.conn, "Submitted ML Engineer")
    _seed_reviewed_job(
        app.state.conn,
        company_name="Example AI",
        job_title="Queued ML Engineer",
        label="Strong fit",
        target_profile_id=profile_id,
    )
    queued_job_id = _job_id_for_title(app.state.conn, "Queued ML Engineer")
    for job_id in (prepared_job_id, submitted_job_id, queued_job_id):
        record_job_decision(
            app.state.conn,
            job_id=job_id,
            target_profile_id=profile_id,
            decision="saved",
        )
    client = TestClient(app)
    client.post(
        f"/jobs/{prepared_job_id}/application-packet",
        data={"target_profile_id": str(profile_id)},
    )
    client.post(
        f"/jobs/{submitted_job_id}/application-packet",
        data={"target_profile_id": str(profile_id)},
    )
    packet_id = app.state.conn.execute(
        """
        SELECT id
        FROM application_packets
        WHERE job_id = ?
        """,
        (submitted_job_id,),
    ).fetchone()["id"]
    client.post(
        f"/application-packets/{packet_id}/status",
        data={"target_profile_id": str(profile_id), "status": "submitted"},
    )

    response = client.get(f"/dashboard/saved?target_profile_id={profile_id}")

    assert response.status_code == 200
    assert "Application" in response.text
    assert "Prepared" in response.text
    assert "Submitted" in response.text
    assert "Not prepared" in response.text
    assert "https://jobs.example/apply" in response.text


def test_saved_jobs_csv_includes_application_packet_status():
    app = create_app()
    profile_id = _seed_reviewed_job(
        app.state.conn,
        company_name="Example AI",
        job_title="Prepared ML Engineer",
        label="Strong fit",
    )
    job_id = _job_id_for_title(app.state.conn, "Prepared ML Engineer")
    record_job_decision(
        app.state.conn,
        job_id=job_id,
        target_profile_id=profile_id,
        decision="saved",
    )
    _seed_private_resume_section(app.state.conn, profile_id, "PRIVATE RESUME TEXT")
    client = TestClient(app)
    client.post(
        f"/jobs/{job_id}/application-packet",
        data={"target_profile_id": str(profile_id)},
    )

    response = client.get(f"/dashboard/saved.csv?target_profile_id={profile_id}")

    rows = list(csv.DictReader(io.StringIO(response.text)))
    assert response.status_code == 200
    assert rows[0]["packet_status"] == "prepared"
    assert rows[0]["manual_submit_url"] == "https://jobs.example/apply"
    assert "PRIVATE RESUME TEXT" not in response.text


def test_saved_jobs_csv_respects_query_and_sort():
    app = create_app()
    profile_id = _seed_saved_job(
        app.state.conn,
        company_name="OpenAI",
        job_title="OpenAI Senior MLE",
        fit_score=70,
    )
    _seed_saved_job(
        app.state.conn,
        company_name="OpenAI",
        job_title="OpenAI Staff MLE",
        fit_score=95,
        target_profile_id=profile_id,
    )
    _seed_saved_job(
        app.state.conn,
        company_name="Anthropic",
        job_title="Anthropic MLE",
        fit_score=99,
        target_profile_id=profile_id,
    )
    client = TestClient(app)

    response = client.get(
        f"/dashboard/saved.csv?target_profile_id={profile_id}&q=openai&sort=score"
    )

    assert response.status_code == 200
    reader = csv.DictReader(io.StringIO(response.text))
    rows = list(reader)
    titles = [row["title"] for row in rows]
    assert titles == ["OpenAI Staff MLE", "OpenAI Senior MLE"]
    assert all(row["company"] == "OpenAI" for row in rows)


def test_saved_jobs_export_link_includes_filter_and_sort():
    app = create_app()
    profile_id = _seed_saved_job(
        app.state.conn,
        company_name="OpenAI",
        job_title="OpenAI Senior MLE",
    )
    client = TestClient(app)

    response = client.get(
        f"/dashboard/saved?target_profile_id={profile_id}&q=foo&sort=score"
    )

    assert response.status_code == 200
    assert (
        f'href="/dashboard/saved.csv?target_profile_id={profile_id}&q=foo&sort=score"'
        in response.text
    )


def test_saved_jobs_csv_unknown_sort_falls_back_to_recent():
    app = create_app()
    profile_id = _seed_saved_job(
        app.state.conn,
        company_name="OpenAI",
        job_title="Older MLE",
        fit_score=50,
    )
    _seed_saved_job(
        app.state.conn,
        company_name="OpenAI",
        job_title="Newer MLE",
        fit_score=99,
        target_profile_id=profile_id,
    )
    client = TestClient(app)

    response = client.get(
        f"/dashboard/saved.csv?target_profile_id={profile_id}&sort=garbage"
    )

    assert response.status_code == 200
    reader = csv.DictReader(io.StringIO(response.text))
    titles = [row["title"] for row in reader]
    assert titles == ["Newer MLE", "Older MLE"]


def test_dashboard_mismatch_risks_show_risk_reasons():
    app = create_app()
    profile_id = _seed_reviewed_job(
        app.state.conn,
        company_name="Example AI",
        job_title="Risky Engineer",
        label="Mismatch risk",
    )
    app.state.conn.execute(
        "UPDATE fit_reviews SET risks_json = ? WHERE target_profile_id = ?",
        ('["role_needs_review", "location_mismatch"]', profile_id),
    )
    app.state.conn.commit()
    client = TestClient(app)

    response = client.get(f"/dashboard?target_profile_id={profile_id}")

    assert response.status_code == 200
    assert "mismatch-risks" in response.text
    assert 'class="job-risks"' in response.text
    assert "role_needs_review" in response.text
    assert "location_mismatch" in response.text


def test_dashboard_renders_catalog_freshness_from_latest_succeeded_run():
    app = create_app()
    profile_id = _seed_reviewed_job(
        app.state.conn,
        company_name="Example AI",
        job_title="Senior Machine Learning Engineer",
        label="Strong fit",
    )
    app.state.conn.execute(
        "INSERT INTO ingestion_runs (started_at, finished_at, status) VALUES (?, ?, ?)",
        ("2026-05-08T03:00:00", "2026-05-08T03:05:00", "succeeded"),
    )
    app.state.conn.execute(
        "INSERT INTO ingestion_runs (started_at, finished_at, status) VALUES (?, ?, ?)",
        ("2026-05-09T12:00:00", "2026-05-09T12:07:00", "succeeded"),
    )
    app.state.conn.execute(
        "INSERT INTO ingestion_runs (started_at, status) VALUES (?, ?)",
        ("2026-05-10T01:00:00", "running"),
    )
    app.state.conn.commit()
    client = TestClient(app)

    response = client.get(f"/dashboard?target_profile_id={profile_id}")

    assert response.status_code == 200
    assert 'class="catalog-freshness"' in response.text
    assert "2026-05-09T12:07:00" in response.text
    assert "2026-05-08T03:05:00" not in response.text


def test_dashboard_freshness_message_when_no_runs():
    client = TestClient(create_app())

    response = client.get("/dashboard")

    assert response.status_code == 200
    assert 'class="catalog-freshness"' in response.text
    assert "Catalog has not been refreshed yet." in response.text


def test_dashboard_onboarding_state_still_shows_freshness():
    app = create_app()
    app.state.conn.execute(
        "INSERT INTO ingestion_runs (started_at, finished_at, status) VALUES (?, ?, ?)",
        ("2026-05-09T12:00:00", "2026-05-09T12:07:00", "succeeded"),
    )
    app.state.conn.commit()
    client = TestClient(app)

    response = client.get("/dashboard")

    assert response.status_code == 200
    assert 'class="catalog-freshness"' in response.text
    assert "2026-05-09T12:07:00" in response.text


def test_decision_save_redirect_appends_status_and_renders_flash():
    app = create_app()
    profile_id = _seed_reviewed_job(
        app.state.conn,
        company_name="Example AI",
        job_title="Senior Machine Learning Engineer",
        label="Strong fit",
    )
    job_id = _job_id_for_title(app.state.conn, "Senior Machine Learning Engineer")
    client = TestClient(app)

    response = client.post(
        f"/jobs/{job_id}/decision",
        data={
            "target_profile_id": profile_id,
            "decision": "saved",
            "return_to": f"/dashboard?target_profile_id={profile_id}",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert "decision_status=saved" in response.headers["location"]
    landing = client.get(response.headers["location"])
    assert landing.status_code == 200
    assert 'class="flash"' in landing.text
    assert "Job saved" in landing.text


def test_decision_hide_redirect_appends_status_and_renders_flash():
    app = create_app()
    profile_id = _seed_reviewed_job(
        app.state.conn,
        company_name="Example AI",
        job_title="Senior Machine Learning Engineer",
        label="Strong fit",
    )
    job_id = _job_id_for_title(app.state.conn, "Senior Machine Learning Engineer")
    client = TestClient(app)

    response = client.post(
        f"/jobs/{job_id}/decision",
        data={
            "target_profile_id": profile_id,
            "decision": "hidden",
            "return_to": f"/dashboard?target_profile_id={profile_id}",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert "decision_status=hidden" in response.headers["location"]
    landing = client.get(response.headers["location"])
    assert "Job hidden" in landing.text


def test_decision_clear_redirect_appends_status_and_renders_flash():
    app = create_app()
    profile_id = _seed_reviewed_job(
        app.state.conn,
        company_name="Example AI",
        job_title="Senior Machine Learning Engineer",
        label="Strong fit",
    )
    job_id = _job_id_for_title(app.state.conn, "Senior Machine Learning Engineer")
    record_job_decision(
        app.state.conn,
        job_id=job_id,
        target_profile_id=profile_id,
        decision="saved",
    )
    client = TestClient(app)

    response = client.post(
        f"/jobs/{job_id}/decision",
        data={
            "target_profile_id": profile_id,
            "decision": "clear",
            "return_to": f"/dashboard?target_profile_id={profile_id}",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert "decision_status=cleared" in response.headers["location"]
    landing = client.get(response.headers["location"])
    assert "Decision cleared" in landing.text


def test_dashboard_ignores_unknown_decision_status():
    client = TestClient(create_app())

    response = client.get("/dashboard?decision_status=garbage")

    assert response.status_code == 200
    assert 'class="flash"' not in response.text


def test_job_detail_external_links_are_safe():
    app = create_app()
    profile_id = _seed_reviewed_job(
        app.state.conn,
        company_name="Example AI",
        job_title="Senior Machine Learning Engineer",
        label="Strong fit",
    )
    job_id = _job_id_for_title(app.state.conn, "Senior Machine Learning Engineer")
    client = TestClient(app)

    response = client.get(f"/jobs/{job_id}?target_profile_id={profile_id}")

    assert response.status_code == 200
    assert (
        '<a href="https://jobs.example/apply" '
        'rel="noopener noreferrer" target="_blank">'
    ) in response.text
    assert (
        '<a href="https://boards.greenhouse.io/example/jobs/1" '
        'rel="noopener noreferrer" target="_blank">'
    ) in response.text


def test_job_detail_does_not_render_adjacent_private_data():
    app = create_app()
    profile_id = _seed_reviewed_job(
        app.state.conn,
        company_name="Example AI",
        job_title="Senior Machine Learning Engineer",
        label="Strong fit",
    )
    job_id = _job_id_for_title(app.state.conn, "Senior Machine Learning Engineer")
    _seed_private_resume_section(app.state.conn, profile_id, "PRIVATE RESUME TEXT")
    app.state.conn.execute(
        """
        INSERT INTO llm_requests (
          model,
          feature,
          schema_version,
          status,
          request_hash,
          response_json
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            "test-model",
            "fit_gate",
            "v1",
            "succeeded",
            "hash",
            json.dumps(
                {
                    "private_prompt": "PRIVATE PROMPT",
                    "cookie": "session=secret-cookie",
                    "token": "secret-token",
                },
                sort_keys=True,
            ),
        ),
    )
    app.state.conn.execute(
        """
        INSERT INTO admin_audit_events (
          action,
          target_type,
          target_id,
          before_json,
          after_json
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            "review_friction",
            "source_friction_event",
            "1",
            json.dumps({"raw_resume_text": "PRIVATE AUDIT RESUME"}, sort_keys=True),
            json.dumps({"browser_profile": "PRIVATE BROWSER PROFILE"}, sort_keys=True),
        ),
    )
    app.state.conn.execute(
        """
        INSERT INTO source_friction_events (
          event_type,
          url,
          details_json
        )
        VALUES (?, ?, ?)
        """,
        (
            "blocked_response",
            "https://boards.greenhouse.io/example",
            json.dumps(
                {
                    "raw_source_payload": "PRIVATE SOURCE PAYLOAD",
                    "api_key": "secret-api-key",
                },
                sort_keys=True,
            ),
        ),
    )
    app.state.conn.commit()
    client = TestClient(app)

    response = client.get(f"/jobs/{job_id}?target_profile_id={profile_id}")

    assert response.status_code == 200
    assert "Senior Machine Learning Engineer" in response.text
    assert "Example AI" in response.text
    assert "Strong fit" in response.text
    assert "matches role" in response.text
    assert "PRIVATE RESUME TEXT" not in response.text
    assert "PRIVATE PROMPT" not in response.text
    assert "secret-cookie" not in response.text
    assert "secret-token" not in response.text
    assert "PRIVATE AUDIT RESUME" not in response.text
    assert "PRIVATE BROWSER PROFILE" not in response.text
    assert "PRIVATE SOURCE PAYLOAD" not in response.text
    assert "secret-api-key" not in response.text


def test_job_detail_decision_returns_to_detail_page():
    app = create_app()
    profile_id = _seed_reviewed_job(
        app.state.conn,
        company_name="Example AI",
        job_title="Senior Machine Learning Engineer",
        label="Strong fit",
    )
    job_id = _job_id_for_title(app.state.conn, "Senior Machine Learning Engineer")
    client = TestClient(app)
    return_to = f"/jobs/{job_id}?target_profile_id={profile_id}"

    response = client.post(
        f"/jobs/{job_id}/decision",
        data={
            "target_profile_id": str(profile_id),
            "decision": "saved",
            "return_to": return_to,
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == f"{return_to}&decision_status=saved"


def test_job_decision_ignores_external_return_to():
    app = create_app()
    profile_id = _seed_reviewed_job(
        app.state.conn,
        company_name="Example AI",
        job_title="Senior Machine Learning Engineer",
        label="Strong fit",
    )
    job_id = _job_id_for_title(app.state.conn, "Senior Machine Learning Engineer")
    client = TestClient(app)

    response = client.post(
        f"/jobs/{job_id}/decision",
        data={
            "target_profile_id": str(profile_id),
            "decision": "saved",
            "return_to": "https://evil.example/phish",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == (
        f"/dashboard?target_profile_id={profile_id}&decision_status=saved"
    )


def test_saved_jobs_page_requires_target_profile():
    client = TestClient(create_app())

    response = client.get("/dashboard/saved")

    assert response.status_code == 400
    assert "target_profile_id is required" in response.text


def test_saved_jobs_page_handles_empty_state():
    app = create_app()
    profile_id = _seed_reviewed_job(
        app.state.conn,
        company_name="Example AI",
        job_title="Senior Machine Learning Engineer",
        label="Strong fit",
    )
    client = TestClient(app)

    response = client.get(f"/dashboard/saved?target_profile_id={profile_id}")

    assert response.status_code == 200
    assert "Saved jobs" in response.text
    assert "No saved jobs" in response.text


def test_saved_jobs_page_lists_saved_jobs_and_excludes_hidden_private_text():
    app = create_app()
    profile_id = _seed_reviewed_job(
        app.state.conn,
        company_name="Example AI",
        job_title="Saved ML Engineer",
        label="Strong fit",
    )
    saved_job_id = _job_id_for_title(app.state.conn, "Saved ML Engineer")
    _seed_reviewed_job(
        app.state.conn,
        company_name="Example AI",
        job_title="Hidden ML Engineer",
        label="Strong fit",
        target_profile_id=profile_id,
    )
    hidden_job_id = _job_id_for_title(app.state.conn, "Hidden ML Engineer")
    record_job_decision(
        app.state.conn,
        job_id=saved_job_id,
        target_profile_id=profile_id,
        decision="saved",
        notes="send to shortlist",
    )
    record_job_decision(
        app.state.conn,
        job_id=hidden_job_id,
        target_profile_id=profile_id,
        decision="hidden",
    )
    _seed_private_resume_section(app.state.conn, profile_id, "PRIVATE RESUME TEXT")
    client = TestClient(app)

    response = client.get(f"/dashboard/saved?target_profile_id={profile_id}")

    assert response.status_code == 200
    assert "Saved jobs" in response.text
    assert "Saved ML Engineer" in response.text
    assert "Example AI" in response.text
    assert "90" in response.text
    assert "Strong fit" in response.text
    assert "Review" in response.text
    assert "send to shortlist" in response.text
    assert "https://jobs.example/apply" in response.text
    assert "https://boards.greenhouse.io/example/jobs/1" in response.text
    assert f"/jobs/{saved_job_id}?target_profile_id={profile_id}" in response.text
    assert f'action="/jobs/{saved_job_id}/application-packet"' in response.text
    assert "Hidden ML Engineer" not in response.text
    assert "PRIVATE RESUME TEXT" not in response.text


def test_saved_jobs_external_links_are_safe():
    app = create_app()
    profile_id = _seed_reviewed_job(
        app.state.conn,
        company_name="Example AI",
        job_title="Saved ML Engineer",
        label="Strong fit",
    )
    saved_job_id = _job_id_for_title(app.state.conn, "Saved ML Engineer")
    record_job_decision(
        app.state.conn,
        job_id=saved_job_id,
        target_profile_id=profile_id,
        decision="saved",
    )
    client = TestClient(app)

    response = client.get(f"/dashboard/saved?target_profile_id={profile_id}")

    assert response.status_code == 200
    assert (
        '<a href="https://jobs.example/apply" '
        'rel="noopener noreferrer" target="_blank">Apply</a>'
    ) in response.text
    assert (
        '<a href="https://boards.greenhouse.io/example/jobs/1" '
        'rel="noopener noreferrer" target="_blank">Source</a>'
    ) in response.text


def test_saved_jobs_page_can_clear_saved_decision_in_place():
    app = create_app()
    profile_id = _seed_reviewed_job(
        app.state.conn,
        company_name="Example AI",
        job_title="Saved ML Engineer",
        label="Strong fit",
    )
    saved_job_id = _job_id_for_title(app.state.conn, "Saved ML Engineer")
    record_job_decision(
        app.state.conn,
        job_id=saved_job_id,
        target_profile_id=profile_id,
        decision="saved",
        notes="send to shortlist",
    )
    client = TestClient(app)

    page = client.get(f"/dashboard/saved?target_profile_id={profile_id}")
    response = client.post(
        f"/jobs/{saved_job_id}/decision",
        data={
            "target_profile_id": str(profile_id),
            "decision": "clear",
            "return_to": f"/dashboard/saved?target_profile_id={profile_id}",
        },
        follow_redirects=False,
    )
    refreshed = client.get(f"/dashboard/saved?target_profile_id={profile_id}")

    assert f'action="/jobs/{saved_job_id}/decision"' in page.text
    assert 'name="decision" value="clear"' in page.text
    assert response.status_code == 303
    assert response.headers["location"] == (
        f"/dashboard/saved?target_profile_id={profile_id}&decision_status=cleared"
    )
    assert "Saved ML Engineer" not in refreshed.text
    assert "No saved jobs" in refreshed.text


def test_saved_jobs_page_searches_company_title_recommendation_and_notes():
    app = create_app()
    profile_id = _seed_saved_job(
        app.state.conn,
        company_name="Alpha AI",
        job_title="Ranking Engineer",
        recommendation="Review alpha team",
        notes="ask about retrieval",
        fit_score=91,
    )
    _seed_saved_job(
        app.state.conn,
        company_name="Beta Labs",
        job_title="Platform Engineer",
        recommendation="Review platform",
        notes="infra team",
        fit_score=80,
        target_profile_id=profile_id,
    )
    client = TestClient(app)

    company_response = client.get(f"/dashboard/saved?target_profile_id={profile_id}&q=alpha")
    note_response = client.get(
        f"/dashboard/saved?target_profile_id={profile_id}&q=retrieval"
    )

    assert company_response.status_code == 200
    assert "Alpha AI" in company_response.text
    assert "Beta Labs" not in company_response.text
    assert note_response.status_code == 200
    assert "Ranking Engineer" in note_response.text
    assert "Platform Engineer" not in note_response.text


def test_saved_jobs_page_shows_filter_empty_state():
    app = create_app()
    profile_id = _seed_saved_job(
        app.state.conn,
        company_name="Alpha AI",
        job_title="Ranking Engineer",
    )
    client = TestClient(app)

    response = client.get(f"/dashboard/saved?target_profile_id={profile_id}&q=nomatch")

    assert response.status_code == 200
    assert "No saved jobs match your filters" in response.text
    assert "No saved jobs</p>" not in response.text


def test_saved_jobs_page_sorts_by_score_company_and_title():
    app = create_app()
    profile_id = _seed_saved_job(
        app.state.conn,
        company_name="Beta Labs",
        job_title="Zeta Engineer",
        fit_score=70,
    )
    _seed_saved_job(
        app.state.conn,
        company_name="Alpha AI",
        job_title="Alpha Engineer",
        fit_score=95,
        target_profile_id=profile_id,
    )
    client = TestClient(app)

    score_response = client.get(
        f"/dashboard/saved?target_profile_id={profile_id}&sort=score"
    )
    company_response = client.get(
        f"/dashboard/saved?target_profile_id={profile_id}&sort=company"
    )
    title_response = client.get(
        f"/dashboard/saved?target_profile_id={profile_id}&sort=title"
    )

    assert score_response.text.index("Alpha AI") < score_response.text.index("Beta Labs")
    assert company_response.text.index("Alpha AI") < company_response.text.index(
        "Beta Labs"
    )
    assert title_response.text.index("Alpha Engineer") < title_response.text.index(
        "Zeta Engineer"
    )


def test_saved_jobs_page_invalid_sort_falls_back_to_recent_and_csv_filters():
    app = create_app()
    profile_id = _seed_saved_job(
        app.state.conn,
        company_name="Alpha AI",
        job_title="Alpha Engineer",
        fit_score=95,
    )
    _seed_saved_job(
        app.state.conn,
        company_name="Beta Labs",
        job_title="Beta Engineer",
        fit_score=70,
        target_profile_id=profile_id,
    )
    client = TestClient(app)

    response = client.get(f"/dashboard/saved?target_profile_id={profile_id}&sort=bad")
    csv_response = client.get(
        f"/dashboard/saved.csv?target_profile_id={profile_id}&q=nomatch&sort=score"
    )

    assert response.status_code == 200
    assert 'value="recent" selected' in response.text
    assert csv_response.status_code == 200
    assert "Alpha Engineer" not in csv_response.text
    assert "Beta Engineer" not in csv_response.text


def test_saved_jobs_export_requires_target_profile():
    client = TestClient(create_app())

    response = client.get("/dashboard/saved.csv")

    assert response.status_code == 400
    assert "target_profile_id is required" in response.text


def test_saved_jobs_export_csv_is_saved_only_and_private_text_free():
    app = create_app()
    profile_id = _seed_reviewed_job(
        app.state.conn,
        company_name="Example AI",
        job_title="Saved ML Engineer",
        label="Strong fit",
    )
    saved_job_id = _job_id_for_title(app.state.conn, "Saved ML Engineer")
    _seed_reviewed_job(
        app.state.conn,
        company_name="Example AI",
        job_title="Hidden ML Engineer",
        label="Strong fit",
        target_profile_id=profile_id,
    )
    hidden_job_id = _job_id_for_title(app.state.conn, "Hidden ML Engineer")
    record_job_decision(
        app.state.conn,
        job_id=saved_job_id,
        target_profile_id=profile_id,
        decision="saved",
        notes="send to shortlist",
    )
    record_job_decision(
        app.state.conn,
        job_id=hidden_job_id,
        target_profile_id=profile_id,
        decision="hidden",
    )
    _seed_private_resume_section(app.state.conn, profile_id, "PRIVATE RESUME TEXT")
    client = TestClient(app)

    response = client.get(f"/dashboard/saved.csv?target_profile_id={profile_id}")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "Saved ML Engineer" in response.text
    assert "send to shortlist" in response.text
    assert "Hidden ML Engineer" not in response.text
    assert "PRIVATE RESUME TEXT" not in response.text


def test_saved_jobs_export_is_profile_scoped_and_spreadsheet_safe():
    app = create_app()
    profile_id = _seed_reviewed_job(
        app.state.conn,
        company_name='@Formula Labs',
        job_title='=HYPERLINK("https://evil.example","Open")',
        label="Strong fit",
    )
    saved_job_id = _job_id_for_title(
        app.state.conn, '=HYPERLINK("https://evil.example","Open")'
    )
    other_profile_id = _seed_reviewed_job(
        app.state.conn,
        company_name="Other Profile AI",
        job_title="Other Profile Saved Engineer",
        label="Strong fit",
    )
    other_job_id = _job_id_for_title(app.state.conn, "Other Profile Saved Engineer")
    record_job_decision(
        app.state.conn,
        job_id=saved_job_id,
        target_profile_id=profile_id,
        decision="saved",
        notes="+SUM(1,2)",
    )
    record_job_decision(
        app.state.conn,
        job_id=other_job_id,
        target_profile_id=other_profile_id,
        decision="saved",
        notes="other profile only",
    )
    client = TestClient(app)

    response = client.get(f"/dashboard/saved.csv?target_profile_id={profile_id}")

    rows = list(csv.DictReader(io.StringIO(response.text)))
    assert response.status_code == 200
    assert len(rows) == 1
    assert rows[0]["company"] == "'@Formula Labs"
    assert rows[0]["title"] == '\'=HYPERLINK("https://evil.example","Open")'
    assert rows[0]["notes"] == "'+SUM(1,2)"
    assert "Other Profile Saved Engineer" not in response.text


def _seed_reviewed_job(
    conn,
    *,
    company_name,
    job_title,
    label,
    target_profile_id=None,
):
    if target_profile_id is None:
        resume_asset_id = conn.execute(
            """
            INSERT INTO resume_assets (original_filename, content_type, storage_path, sha256)
            VALUES (?, ?, ?, ?)
            """,
            ("resume.pdf", "application/pdf", "/tmp/resume.pdf", f"sha-{job_title}"),
        ).lastrowid
        target_profile_id = create_target_profile(
            conn,
            resume_asset_id=resume_asset_id,
            keywords=KEYWORDS,
            preferences=PREFERENCES,
        )

    normalized_name = company_name.casefold()
    company = conn.execute(
        "SELECT id FROM companies WHERE normalized_name = ?",
        (normalized_name,),
    ).fetchone()
    if company is None:
        company_id = conn.execute(
            "INSERT INTO companies (name, normalized_name) VALUES (?, ?)",
            (company_name, normalized_name),
        ).lastrowid
    else:
        company_id = company["id"]

    job_id = conn.execute(
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
            f"job-{job_title}",
            job_title,
            "Engineering",
            "Remote - New York, NY",
            "remote",
            "Full-time",
            "senior",
            "Build ML ranking systems.",
            "Python and PyTorch required.",
            "https://jobs.example/apply",
            "https://boards.greenhouse.io/example/jobs/1",
            f"hash-{job_title}",
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
            90 if label == "Strong fit" else 70,
            label,
            '["matches role"]',
            "[]",
            "Review",
            1,
        ),
    )
    conn.commit()
    return target_profile_id


def _seed_unreviewed_job(
    conn,
    *,
    company_name,
    job_title,
    target_profile_id=None,
):
    if target_profile_id is None:
        resume_asset_id = conn.execute(
            """
            INSERT INTO resume_assets (original_filename, content_type, storage_path, sha256)
            VALUES (?, ?, ?, ?)
            """,
            (
                "resume.pdf",
                "application/pdf",
                "/tmp/resume.pdf",
                f"unreviewed-sha-{job_title}",
            ),
        ).lastrowid
        target_profile_id = create_target_profile(
            conn,
            resume_asset_id=resume_asset_id,
            keywords=KEYWORDS,
            preferences=PREFERENCES,
        )

    normalized_name = company_name.casefold()
    company_id = conn.execute(
        "INSERT INTO companies (name, normalized_name, stage) VALUES (?, ?, ?)",
        (company_name, normalized_name, "growth"),
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
            company_id,
            source_id,
            f"unreviewed-{job_title}",
            job_title,
            "Remote - New York, NY",
            "remote",
            "senior",
            "Build reliable ML systems with Python and PyTorch.",
            "Python, PyTorch, model serving, and LLM evaluation.",
            "https://boards.greenhouse.io/example/jobs/1",
            "https://boards.greenhouse.io/example/jobs/1",
            f"unreviewed-hash-{job_title}",
        ),
    )
    conn.commit()
    return target_profile_id


def _seed_saved_job(
    conn,
    *,
    company_name,
    job_title,
    recommendation="Review",
    notes="",
    fit_score=90,
    target_profile_id=None,
):
    profile_id = _seed_reviewed_job(
        conn,
        company_name=company_name,
        job_title=job_title,
        label="Strong fit",
        target_profile_id=target_profile_id,
    )
    job_id = _job_id_for_title(conn, job_title)
    conn.execute(
        """
        UPDATE fit_reviews
        SET fit_score = ?, recommendation = ?
        WHERE job_id = ? AND target_profile_id = ?
        """,
        (fit_score, recommendation, job_id, profile_id),
    )
    conn.commit()
    record_job_decision(
        conn,
        job_id=job_id,
        target_profile_id=profile_id,
        decision="saved",
        notes=notes,
    )
    return profile_id


def _job_id_for_title(conn, title):
    return conn.execute("SELECT id FROM jobs WHERE title = ?", (title,)).fetchone()["id"]


def _seed_resume_keywords(conn, target_profile_id, keywords):
    resume_asset_id = conn.execute(
        "SELECT resume_asset_id FROM target_profiles WHERE id = ?",
        (target_profile_id,),
    ).fetchone()["resume_asset_id"]
    parse_run_id = conn.execute(
        """
        INSERT INTO resume_parse_runs (
          resume_asset_id,
          parser,
          parser_version,
          status,
          confidence
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (resume_asset_id, "test", "v1", "parsed", 1.0),
    ).lastrowid
    conn.executemany(
        """
        INSERT INTO resume_keywords (
          parse_run_id,
          keyword,
          source_section,
          weight
        )
        VALUES (?, ?, ?, ?)
        """,
        [(parse_run_id, keyword, "skills", 1.0) for keyword in keywords],
    )
    conn.commit()


def _seed_private_resume_section(conn, target_profile_id, text):
    resume_asset_id = conn.execute(
        "SELECT resume_asset_id FROM target_profiles WHERE id = ?",
        (target_profile_id,),
    ).fetchone()["resume_asset_id"]
    parse_run_id = conn.execute(
        """
        INSERT INTO resume_parse_runs (
          resume_asset_id,
          parser,
          parser_version,
          status,
          confidence
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (resume_asset_id, "test", "v1", "succeeded", 1.0),
    ).lastrowid
    section_id = conn.execute(
        """
        INSERT INTO resume_sections (
          parse_run_id,
          section_type,
          heading,
          text,
          sort_order
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (parse_run_id, "experience", "Experience", text, 1),
    ).lastrowid
    conn.commit()
    return int(section_id)


def _seed_resume_rewrite_suggestion(
    conn,
    *,
    target_profile_id,
    section_id,
    suggestion_text,
    status="draft",
):
    resume_asset_id = conn.execute(
        "SELECT resume_asset_id FROM target_profiles WHERE id = ?",
        (target_profile_id,),
    ).fetchone()["resume_asset_id"]
    suggestion_id = conn.execute(
        """
        INSERT INTO resume_rewrite_suggestions (
          resume_asset_id,
          target_profile_id,
          section_id,
          suggestion_text,
          status
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (resume_asset_id, target_profile_id, section_id, suggestion_text, status),
    ).lastrowid
    conn.commit()
    return int(suggestion_id)
