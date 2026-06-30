import time

import jwt
from fastapi.testclient import TestClient

from ml_job_swarm.app import create_app
from ml_job_swarm.cloud_runtime import create_run, list_run_events
from ml_job_swarm.profile import create_target_profile

JWT_SECRET = "test-jwt-secret-for-hosted-auth-32b"

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


def test_cloud_runs_page_lists_user_runs(tmp_path):
    app = create_app(tmp_path / "cloud-ui-list.db")
    run = create_run(
        app.state.conn,
        user_id="operator-1",
        requested_action="continue_local_workflow",
        input_manifest={"target_profile_id": 1},
    )
    client = TestClient(app)

    response = client.get("/cloud/runs")

    assert response.status_code == 200
    assert 'class="cloud-runs-table"' in response.text
    assert f'data-cloud-run-id="{run["id"]}"' in response.text
    assert f'href="/cloud/runs/{run["id"]}"' in response.text
    assert 'action="/cloud/runs/start"' in response.text
    assert "Start cloud run" in response.text


def test_cloud_run_detail_page_exposes_status_events_and_manifest(tmp_path):
    app = create_app(tmp_path / "cloud-ui-detail.db")
    run = create_run(
        app.state.conn,
        user_id="operator-1",
        requested_action="continue_local_workflow",
        input_manifest={"target_profile_id": 1, "api_token": "secret-value"},
    )
    client = TestClient(app)

    response = client.get(f"/cloud/runs/{run['id']}")

    assert response.status_code == 200
    assert 'class="cloud-run-summary-panel"' in response.text
    assert 'class="cloud-run-events-panel"' in response.text
    assert 'class="cloud-run-manifest-panel"' in response.text
    assert "queued" in response.text
    assert "run_created" in response.text
    assert "secret-value" not in response.text
    assert f'action="/cloud/runs/{run["id"]}/cancel"' in response.text


def test_cloud_run_cancel_form_redirects_and_marks_run_canceled(tmp_path):
    app = create_app(tmp_path / "cloud-ui-cancel.db")
    run = create_run(
        app.state.conn,
        user_id="operator-1",
        requested_action="continue_local_workflow",
        input_manifest={"target_profile_id": 1},
    )
    client = TestClient(app)

    response = client.post(
        f"/cloud/runs/{run['id']}/cancel",
        data={"reason": "Stopped from UI"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == f"/cloud/runs/{run['id']}?cancel_status=ok"
    detail = client.get(f"/cloud/runs/{run['id']}")
    assert detail.status_code == 200
    assert "canceled" in detail.text
    assert f'action="/cloud/runs/{run["id"]}/cancel"' not in detail.text


def test_cloud_run_start_form_creates_run_and_redirects(tmp_path):
    app = create_app(tmp_path / "cloud-ui-start.db")
    target_profile_id = _seed_target_profile(app.state.conn)
    client = TestClient(app)

    response = client.post(
        "/cloud/runs/start",
        data={
            "target_profile_id": str(target_profile_id),
            "prepare_packets": "on",
            "llm_consent": "on",
            "user_id": "operator-1",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "continue_local_workflow" in response.text
    assert "Cloud run queued." in response.text
    run_id = response.request.url.path.rsplit("/", 1)[-1]
    events = list_run_events(app.state.conn, run_id)
    assert events[0]["event_type"] == "run_created"


def test_dashboard_shows_active_cloud_run_panel(tmp_path):
    app = create_app(tmp_path / "cloud-ui-dashboard.db")
    target_profile_id = _seed_target_profile(app.state.conn)
    run = create_run(
        app.state.conn,
        user_id="operator-1",
        requested_action="continue_local_workflow",
        input_manifest={"target_profile_id": target_profile_id},
    )
    client = TestClient(app)

    response = client.get(f"/dashboard?target_profile_id={target_profile_id}")

    assert response.status_code == 200
    assert 'class="cloud-run-panel"' in response.text
    assert "Active cloud run" in response.text
    assert run["current_stage"] in response.text or "queued" in response.text
    assert f'href="/cloud/runs/{run["id"]}"' in response.text
    assert "View run details" in response.text


def test_cloud_ui_routes_use_app_shell(tmp_path):
    app = create_app(tmp_path / "cloud-ui-shell.db")
    run = create_run(
        app.state.conn,
        user_id="operator-1",
        requested_action="continue_local_workflow",
        input_manifest={"target_profile_id": 1},
    )
    client = TestClient(app)

    for path, active_href in (
        ("/cloud/runs", "/cloud/runs"),
        (f"/cloud/runs/{run['id']}", "/cloud/runs"),
    ):
        response = client.get(path)

        assert response.status_code == 200
        assert 'class="app-shell"' in response.text
        assert 'class="app-sidebar"' in response.text
        assert 'class="app-content"' in response.text
        assert f'href="{active_href}" aria-current="page"' in response.text


def test_cloud_ui_scopes_runs_to_authenticated_user(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-test-key")
    monkeypatch.setenv("SUPABASE_JWT_SECRET", JWT_SECRET)
    app = create_app(tmp_path / "cloud-ui-auth.db")
    run_a = create_run(
        app.state.conn,
        user_id="user-a",
        requested_action="continue_local_workflow",
        input_manifest={"target_profile_id": 1},
    )
    create_run(
        app.state.conn,
        user_id="user-b",
        requested_action="continue_local_workflow",
        input_manifest={"target_profile_id": 1},
    )
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {_make_token('user-a')}"}

    listed = client.get("/cloud/runs", headers=headers)
    assert listed.status_code == 200
    assert run_a["id"] in listed.text
    assert listed.text.count('data-cloud-run-id="') == 1

    blocked = client.get("/cloud/runs", headers={"Authorization": f"Bearer {_make_token('user-b')}"})
    assert run_a["id"] not in blocked.text

    missing = client.get(f"/cloud/runs/{run_a['id']}", headers={"Authorization": f"Bearer {_make_token('user-b')}"})
    assert missing.status_code == 404


def test_static_css_contains_cloud_run_rules(tmp_path):
    client = TestClient(create_app(tmp_path / "cloud-ui-css.db"))

    response = client.get("/static/app.css")

    assert response.status_code == 200
    for selector in (
        ".cloud-run-panel",
        ".cloud-runs-table",
        ".cloud-run-manifest",
        ".cloud-status-badge",
    ):
        assert selector in response.text


def _seed_target_profile(conn):
    resume_asset_id = conn.execute(
        """
        INSERT INTO resume_assets (original_filename, content_type, storage_path, sha256)
        VALUES (?, ?, ?, ?)
        """,
        ("resume.pdf", "application/pdf", "/tmp/resume.pdf", "cloud-ui-sha"),
    ).lastrowid
    return create_target_profile(
        conn,
        resume_asset_id=resume_asset_id,
        keywords=KEYWORDS,
        preferences=PREFERENCES,
    )


def _make_token(subject: str) -> str:
    now = int(time.time())
    payload = {
        "sub": subject,
        "aud": "authenticated",
        "exp": now + 3600,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")
