from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


class SQLiteDatabase:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection

    @property
    def native(self) -> sqlite3.Connection:
        return self._conn

    def execute(
        self,
        sql: str,
        params: tuple[Any, ...] | list[Any] = (),
    ) -> sqlite3.Cursor:
        return self._conn.execute(sql, params)

    def executemany(
        self,
        sql: str,
        params: list[tuple[Any, ...]],
    ) -> sqlite3.Cursor:
        return self._conn.executemany(sql, params)

    def executescript(self, sql: str) -> None:
        self._conn.executescript(sql)

    def commit(self) -> None:
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()


def connect_sqlite(
    path: str | Path = ":memory:",
    *,
    check_same_thread: bool = True,
) -> SQLiteDatabase:
    conn = sqlite3.connect(str(path), check_same_thread=check_same_thread)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return SQLiteDatabase(conn)