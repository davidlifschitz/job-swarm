import os

import pytest

from ml_job_swarm.db.dialect import BackendKind
from ml_job_swarm.db.factory import backend_kind_from_env, connect_from_env
from ml_job_swarm.db.protocol import Database
from ml_job_swarm.db.sqlite_backend import SQLiteDatabase
from ml_job_swarm.store import init_db


def test_backend_kind_defaults_to_sqlite(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert backend_kind_from_env() == BackendKind.SQLITE


def test_backend_kind_uses_postgres_when_database_url_set(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/jobs")
    assert backend_kind_from_env() == BackendKind.POSTGRES


def test_connect_from_env_returns_sqlite_database(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    db_path = tmp_path / "factory.db"
    monkeypatch.setenv("ML_JOB_SWARM_DB_PATH", str(db_path))

    db = connect_from_env()

    assert isinstance(db, SQLiteDatabase)
    assert isinstance(db, Database)
    init_db(db)
    row = db.execute("SELECT COUNT(*) AS count FROM companies").fetchone()
    assert int(row["count"]) == 0
    db.close()


def test_connect_from_env_postgres_requires_dependency(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/jobs")
    try:
        import psycopg  # noqa: F401
    except ImportError:
        with pytest.raises(RuntimeError, match="psycopg"):
            connect_from_env()
    else:
        os.environ.pop("DATABASE_URL", None)