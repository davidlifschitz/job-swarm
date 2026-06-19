from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from typing import TYPE_CHECKING

from ml_job_swarm.db.dialect import BackendKind
from ml_job_swarm.db.protocol import Database

if TYPE_CHECKING:
    from ml_job_swarm.db.postgres_backend import PostgresDatabase

StoreConnection = sqlite3.Connection | Database


def backend_kind_from_conn(conn: StoreConnection) -> BackendKind:
    from ml_job_swarm.db.postgres_backend import PostgresDatabase

    if isinstance(conn, PostgresDatabase):
        return BackendKind.POSTGRES
    return BackendKind.SQLITE


@contextmanager
def connection_transaction(conn: StoreConnection) -> Iterator[StoreConnection]:
    from ml_job_swarm.db.postgres_backend import PostgresDatabase

    if isinstance(conn, PostgresDatabase):
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        return

    if isinstance(conn, sqlite3.Connection):
        with conn:
            yield conn
        return

    try:
        yield conn
        conn.commit()
    except Exception:
        if hasattr(conn, "rollback"):
            conn.rollback()
        raise