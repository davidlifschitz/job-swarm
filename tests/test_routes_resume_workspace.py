import json

from fastapi.testclient import TestClient

from ml_job_swarm.app import create_app
from ml_job_swarm.llm import ResumeRewriteResponse
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


class InvalidRewriteClient(FakeRewriteClient):
    def rewrite_section(self, payload):
        self.calls.append(payload)
        return {
            "section_id": payload["section_id"],
            "replacement_text": "",
            "rationale": "bad",
            "raw_resume_text": "PRIVATE RESUME SECTION",
        }


class ErrorRewriteClient(FakeRewriteClient):
    def rewrite_section(self, payload):
        self.calls.append(payload)
        raise RuntimeError("provider timeout")


def test_resume_sections_render_as_clickable_items():
    app = create_app()
    target_profile_id, section_id = _seed_profile_with_section(app.state.conn)
    client = TestClient(app)

    response = client.get(f"/dashboard?target_profile_id={target_profile_id}")

    assert response.status_code == 200
    assert f'data-section-id="{section_id}"' in response.text
    assert "Experience" in response.text
    assert "Built ML systems." in response.text


def test_dashboard_resume_sections_include_rewrite_forms():
    app = create_app()
    target_profile_id, section_id = _seed_profile_with_section(app.state.conn)
    client = TestClient(app)

    response = client.get(f"/dashboard?target_profile_id={target_profile_id}")

    assert response.status_code == 200
    assert 'action="/resume/rewrite"' in response.text
    assert f'name="section_id" value="{section_id}"' in response.text
    assert f'name="target_profile_id" value="{target_profile_id}"' in response.text
    assert 'name="llm_consent" value="on"' in response.text
    assert "private_prompt" not in response.text


def test_rewrite_suggestion_requires_section_id():
    client = TestClient(create_app())

    response = client.post("/resume/rewrite", data={"target_profile_id": "1"})

    assert response.status_code == 400
    assert "section_id is required" in response.text


def test_rewrite_suggestion_requires_llm_consent():
    app = create_app()
    target_profile_id, section_id = _seed_profile_with_section(app.state.conn)
    client = TestClient(app)

    response = client.post(
        "/resume/rewrite",
        data={"target_profile_id": str(target_profile_id), "section_id": str(section_id)},
    )

    assert response.status_code == 400
    assert "LLM consent is required" in response.text


def test_rewrite_suggestion_records_llm_metadata():
    app = create_app()
    rewrite_client = FakeRewriteClient()
    app.state.resume_rewrite_client = rewrite_client
    target_profile_id, section_id = _seed_profile_with_section(app.state.conn)
    client = TestClient(app)

    response = client.post(
        "/resume/rewrite",
        data={
            "target_profile_id": str(target_profile_id),
            "section_id": str(section_id),
            "llm_consent": "on",
        },
        follow_redirects=False,
    )

    row = app.state.conn.execute(
        """
        SELECT resume_rewrite_suggestions.suggestion_text,
               llm_requests.feature,
               llm_requests.schema_version,
               llm_requests.status,
               llm_requests.request_hash,
               llm_requests.response_json
        FROM resume_rewrite_suggestions
        JOIN llm_requests ON llm_requests.id = resume_rewrite_suggestions.llm_request_id
        """
    ).fetchone()
    assert response.status_code == 303
    assert response.headers["location"] == f"/dashboard?target_profile_id={target_profile_id}"
    assert rewrite_client.calls[0]["section_id"] == section_id
    assert row["suggestion_text"] == "Built ML serving platform for 80M requests/day."
    assert row["feature"] == "resume_rewrite"
    assert row["schema_version"] == "resume_rewrite.v1"
    assert row["status"] == "succeeded"
    persisted = json.dumps(dict(row), sort_keys=True)
    assert row["request_hash"]
    assert "Built ML systems." not in persisted


def test_rewrite_suggestion_without_target_profile_keeps_success_response():
    app = create_app()
    rewrite_client = FakeRewriteClient()
    app.state.resume_rewrite_client = rewrite_client
    _target_profile_id, section_id = _seed_profile_with_section(app.state.conn)
    client = TestClient(app)

    response = client.post(
        "/resume/rewrite",
        data={
            "section_id": str(section_id),
            "llm_consent": "on",
        },
    )

    assert response.status_code == 200
    assert "Resume rewrite suggestion created" in response.text


def test_invalid_rewrite_response_records_failed_llm_metadata():
    app = create_app()
    app.state.resume_rewrite_client = InvalidRewriteClient()
    target_profile_id, section_id = _seed_profile_with_section(app.state.conn)
    client = TestClient(app)

    response = client.post(
        "/resume/rewrite",
        data={
            "target_profile_id": str(target_profile_id),
            "section_id": str(section_id),
            "llm_consent": "on",
        },
    )

    request = app.state.conn.execute("SELECT * FROM llm_requests").fetchone()
    persisted = json.dumps(dict(request), sort_keys=True)
    assert response.status_code == 502
    assert request["feature"] == "resume_rewrite"
    assert request["status"] == "failed"
    assert "PRIVATE RESUME SECTION" not in persisted


def test_rewrite_client_exception_records_failed_llm_metadata():
    app = create_app()
    app.state.resume_rewrite_client = ErrorRewriteClient()
    target_profile_id, section_id = _seed_profile_with_section(app.state.conn)
    client = TestClient(app)

    response = client.post(
        "/resume/rewrite",
        data={
            "target_profile_id": str(target_profile_id),
            "section_id": str(section_id),
            "llm_consent": "on",
        },
    )

    request = app.state.conn.execute(
        "SELECT feature, status, error FROM llm_requests"
    ).fetchone()
    assert response.status_code == 502
    assert dict(request) == {
        "feature": "resume_rewrite",
        "status": "failed",
        "error": "provider timeout",
    }


def test_accepting_suggestion_updates_generated_suggestion_not_raw_resume():
    app = create_app()
    app.state.resume_rewrite_client = FakeRewriteClient()
    target_profile_id, section_id = _seed_profile_with_section(app.state.conn)
    client = TestClient(app)
    client.post(
        "/resume/rewrite",
        data={
            "target_profile_id": str(target_profile_id),
            "section_id": str(section_id),
            "llm_consent": "on",
        },
    )
    suggestion_id = app.state.conn.execute(
        "SELECT id FROM resume_rewrite_suggestions"
    ).fetchone()["id"]

    response = client.post(f"/resume/suggestions/{suggestion_id}/accept")

    suggestion = app.state.conn.execute(
        "SELECT status, suggestion_text FROM resume_rewrite_suggestions WHERE id = ?",
        (suggestion_id,),
    ).fetchone()
    raw_section = app.state.conn.execute(
        "SELECT text FROM resume_sections WHERE id = ?",
        (section_id,),
    ).fetchone()
    assert response.status_code == 200
    assert suggestion["status"] == "accepted"
    assert suggestion["suggestion_text"] == "Built ML serving platform for 80M requests/day."
    assert raw_section["text"] == "Built ML systems."


def test_dashboard_lists_draft_resume_suggestions_for_active_profile():
    app = create_app()
    target_profile_id, section_id = _seed_profile_with_section(app.state.conn)
    other_profile_id, other_section_id = _seed_profile_with_section(
        app.state.conn, sha="other-workspace-resume-sha"
    )
    suggestion_id = _seed_suggestion(
        app.state.conn,
        target_profile_id=target_profile_id,
        section_id=section_id,
        suggestion_text="Built production ML platform with clear impact.",
    )
    _seed_suggestion(
        app.state.conn,
        target_profile_id=other_profile_id,
        section_id=other_section_id,
        suggestion_text="Other profile suggestion should stay hidden.",
    )
    client = TestClient(app)

    response = client.get(f"/dashboard?target_profile_id={target_profile_id}")

    assert response.status_code == 200
    assert "Resume suggestions" in response.text
    assert f'data-suggestion-id="{suggestion_id}"' in response.text
    assert "Built production ML platform with clear impact." in response.text
    assert "Other profile suggestion should stay hidden." not in response.text
    assert "private_prompt" not in response.text


def test_accepting_suggestion_from_dashboard_redirects_to_profile():
    app = create_app()
    target_profile_id, section_id = _seed_profile_with_section(app.state.conn)
    suggestion_id = _seed_suggestion(
        app.state.conn,
        target_profile_id=target_profile_id,
        section_id=section_id,
        suggestion_text="Built production ML platform with clear impact.",
    )
    client = TestClient(app)

    response = client.post(
        f"/resume/suggestions/{suggestion_id}/accept",
        data={"target_profile_id": str(target_profile_id)},
        follow_redirects=False,
    )

    suggestion = app.state.conn.execute(
        "SELECT status FROM resume_rewrite_suggestions WHERE id = ?",
        (suggestion_id,),
    ).fetchone()
    assert response.status_code == 303
    assert response.headers["location"] == f"/dashboard?target_profile_id={target_profile_id}"
    assert suggestion["status"] == "accepted"


def test_rejecting_suggestion_from_dashboard_updates_status_and_redirects():
    app = create_app()
    target_profile_id, section_id = _seed_profile_with_section(app.state.conn)
    suggestion_id = _seed_suggestion(
        app.state.conn,
        target_profile_id=target_profile_id,
        section_id=section_id,
        suggestion_text="Built production ML platform with clear impact.",
    )
    client = TestClient(app)

    response = client.post(
        f"/resume/suggestions/{suggestion_id}/reject",
        data={"target_profile_id": str(target_profile_id)},
        follow_redirects=False,
    )

    suggestion = app.state.conn.execute(
        "SELECT status FROM resume_rewrite_suggestions WHERE id = ?",
        (suggestion_id,),
    ).fetchone()
    assert response.status_code == 303
    assert response.headers["location"] == f"/dashboard?target_profile_id={target_profile_id}"
    assert suggestion["status"] == "rejected"


def test_accepting_suggestion_for_wrong_profile_returns_404_and_leaves_draft():
    app = create_app()
    target_profile_id, section_id = _seed_profile_with_section(app.state.conn)
    other_profile_id, _ = _seed_profile_with_section(
        app.state.conn, sha="wrong-profile-resume-sha"
    )
    suggestion_id = _seed_suggestion(
        app.state.conn,
        target_profile_id=target_profile_id,
        section_id=section_id,
        suggestion_text="Built production ML platform with clear impact.",
    )
    client = TestClient(app)

    response = client.post(
        f"/resume/suggestions/{suggestion_id}/accept",
        data={"target_profile_id": str(other_profile_id)},
    )

    status = app.state.conn.execute(
        "SELECT status FROM resume_rewrite_suggestions WHERE id = ?",
        (suggestion_id,),
    ).fetchone()["status"]
    assert response.status_code == 404
    assert "Suggestion not found" in response.text
    assert status == "draft"


def test_accepting_rejected_suggestion_leaves_it_rejected_and_creates_no_llm_request():
    app = create_app()
    target_profile_id, section_id = _seed_profile_with_section(app.state.conn)
    suggestion_id = _seed_suggestion(
        app.state.conn,
        target_profile_id=target_profile_id,
        section_id=section_id,
        suggestion_text="Built production ML platform with clear impact.",
        status="rejected",
    )
    client = TestClient(app)

    response = client.post(
        f"/resume/suggestions/{suggestion_id}/accept",
        data={"target_profile_id": str(target_profile_id)},
        follow_redirects=False,
    )

    status = app.state.conn.execute(
        "SELECT status FROM resume_rewrite_suggestions WHERE id = ?",
        (suggestion_id,),
    ).fetchone()["status"]
    llm_count = app.state.conn.execute("SELECT COUNT(*) FROM llm_requests").fetchone()[0]
    assert response.status_code == 303
    assert status == "rejected"
    assert llm_count == 0


def test_rejecting_accepted_suggestion_leaves_it_accepted_and_creates_no_llm_request():
    app = create_app()
    target_profile_id, section_id = _seed_profile_with_section(app.state.conn)
    suggestion_id = _seed_suggestion(
        app.state.conn,
        target_profile_id=target_profile_id,
        section_id=section_id,
        suggestion_text="Built production ML platform with clear impact.",
        status="accepted",
    )
    client = TestClient(app)

    response = client.post(
        f"/resume/suggestions/{suggestion_id}/reject",
        data={"target_profile_id": str(target_profile_id)},
        follow_redirects=False,
    )

    status = app.state.conn.execute(
        "SELECT status FROM resume_rewrite_suggestions WHERE id = ?",
        (suggestion_id,),
    ).fetchone()["status"]
    llm_count = app.state.conn.execute("SELECT COUNT(*) FROM llm_requests").fetchone()[0]
    assert response.status_code == 303
    assert status == "accepted"
    assert llm_count == 0


def test_rejecting_missing_suggestion_returns_404():
    client = TestClient(create_app())

    response = client.post("/resume/suggestions/999/reject")

    assert response.status_code == 404
    assert "Suggestion not found" in response.text


def _seed_profile_with_section(conn, *, sha="workspace-resume-sha"):
    resume_asset_id = conn.execute(
        """
        INSERT INTO resume_assets (original_filename, content_type, storage_path, sha256)
        VALUES (?, ?, ?, ?)
        """,
        ("resume.pdf", "application/pdf", "/tmp/resume.pdf", sha),
    ).lastrowid
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
    return target_profile_id, section_id


def _seed_suggestion(
    conn, *, target_profile_id, section_id, suggestion_text, status="draft"
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
    return suggestion_id
