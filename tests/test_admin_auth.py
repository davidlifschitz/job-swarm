from fastapi.testclient import TestClient

from ml_job_swarm.app import create_app
from tests.conftest import admin_auth_env, auth_headers


def test_html_admin_denies_non_admin_when_supabase_enabled(tmp_path, admin_auth_env):
    client = TestClient(create_app(tmp_path / "html-admin-deny.db"))

    denied = client.get("/admin/sources", headers=auth_headers("regular-user"))
    assert denied.status_code == 403


def test_html_admin_allows_allowlisted_user(tmp_path, admin_auth_env):
    client = TestClient(create_app(tmp_path / "html-admin-allow.db"))

    allowed = client.get("/admin/sources", headers=auth_headers("admin-user"))
    assert allowed.status_code == 200


def test_html_admin_open_in_local_mode(tmp_path):
    client = TestClient(create_app(tmp_path / "html-admin-local.db"))

    response = client.get("/admin/sources")
    assert response.status_code == 200
