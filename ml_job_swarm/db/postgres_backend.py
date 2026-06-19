from __future__ import annotations

from typing import Any


class PostgresCursor:
    def __init__(self, cursor: Any, *, lastrowid: int | None = None) -> None:
        self._cursor = cursor
        self._lastrowid = lastrowid

    @property
    def rowcount(self) -> int:
        return int(self._cursor.rowcount)

    @property
    def lastrowid(self) -> int | None:
        return self._lastrowid

    def fetchone(self) -> Any:
        return self._cursor.fetchone()

    def fetchall(self) -> list[Any]:
        return list(self._cursor.fetchall())


class PostgresDatabase:
    def __init__(self, connection: Any) -> None:
        self._conn = connection

    @property
    def native(self) -> Any:
        return self._conn

    def execute(
        self,
        sql: str,
        params: tuple[Any, ...] | list[Any] = (),
    ) -> PostgresCursor:
        from ml_job_swarm.db.dialect import BackendKind, translate_sql

        translated = translate_sql(sql, BackendKind.POSTGRES)
        cursor = self._conn.cursor()
        cursor.execute(translated, params)
        lastrowid = None
        if translated.lstrip().upper().startswith("INSERT") and "RETURNING" not in translated.upper():
            # Phase B1 will standardize INSERT ... RETURNING id for Postgres.
            lastrowid = None
        return PostgresCursor(cursor, lastrowid=lastrowid)

    def executemany(
        self,
        sql: str,
        params: list[tuple[Any, ...]],
    ) -> PostgresCursor:
        from ml_job_swarm.db.dialect import BackendKind, translate_sql

        translated = translate_sql(sql, BackendKind.POSTGRES)
        cursor = self._conn.cursor()
        cursor.executemany(translated, params)
        return PostgresCursor(cursor)

    def executescript(self, sql: str) -> None:
        from ml_job_swarm.db.postgres_schema import apply_postgres_schema

        apply_postgres_schema(self)

    def commit(self) -> None:
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()


def connect_postgres(database_url: str) -> PostgresDatabase:
    try:
        import psycopg
    except ImportError as exc:
        raise RuntimeError(
            "psycopg is required for DATABASE_URL connections. "
            "Install with: uv sync --extra hosted"
        ) from exc
    conn = psycopg.connect(database_url, row_factory=psycopg.rows.dict_row)
    return PostgresDatabase(conn)