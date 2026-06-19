from __future__ import annotations

import os
from pathlib import Path

from ml_job_swarm.db.dialect import BackendKind
from ml_job_swarm.db.postgres_backend import PostgresDatabase, connect_postgres
from ml_job_swarm.db.protocol import Database
from ml_job_swarm.db.sqlite_backend import SQLiteDatabase, connect_sqlite
from ml_job_swarm.hosting import hosted_paths_from_env


def backend_kind_from_env(env: dict[str, str] | None = None) -> BackendKind:
    source = env if env is not None else os.environ
    database_url = (source.get("DATABASE_URL") or "").strip()
    if database_url:
        return BackendKind.POSTGRES
    return BackendKind.SQLITE


def connect_from_env(
    env: dict[str, str] | None = None,
    *,
    check_same_thread: bool = True,
) -> Database:
    source = env if env is not None else os.environ
    database_url = (source.get("DATABASE_URL") or "").strip()
    if database_url:
        return connect_postgres(database_url)

    paths = hosted_paths_from_env(source)
    db_path = paths["db_path"]
    return connect_sqlite(Path(db_path), check_same_thread=check_same_thread)