import os
from pathlib import Path

from fastapi.testclient import TestClient

from ml_job_swarm.app import create_app_from_env
from ml_job_swarm.hosting import (
    ensure_hosted_directories,
    hosted_paths_from_env,
    hosted_storage_mode,
    uses_postgres_database,
    uses_supabase_resume_storage,
)


def test_hosted_storage_mode_reflects_env(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    assert hosted_storage_mode() == {
        "database_backend": "sqlite",
        "resume_storage_backend": "local",
    }

    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/jobs")
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-role-key")
    assert uses_postgres_database() is True
    assert uses_supabase_resume_storage() is True
    assert hosted_storage_mode() == {
        "database_backend": "postgresql",
        "resume_storage_backend": "supabase",
    }


def test_ensure_hosted_directories_skips_volume_paths_when_postgres_enabled(tmp_path):
    env = {
        "ML_JOB_SWARM_DATA_DIR": str(tmp_path / "cutover-data"),
        "DATABASE_URL": "postgresql://user:pass@localhost:5432/jobs",
        "SUPABASE_URL": "https://example.supabase.co",
        "SUPABASE_SERVICE_ROLE_KEY": "service-role-key",
    }
    paths = hosted_paths_from_env(env)
    ensure_hosted_directories(paths, env=env)

    assert not Path(paths["db_path"]).exists()
    assert not Path(paths["resume_asset_dir"]).exists()


def test_healthz_reports_storage_backends(tmp_path, monkeypatch):
    monkeypatch.setenv("ML_JOB_SWARM_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_URL", raising=False)

    client = TestClient(create_app_from_env())
    health = client.get("/healthz").json()

    assert health["database_backend"] == "sqlite"
    assert health["resume_storage_backend"] == "local"