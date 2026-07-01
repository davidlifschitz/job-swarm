from __future__ import annotations

from enum import Enum


class BackendKind(str, Enum):
    SQLITE = "sqlite"
    POSTGRES = "postgres"


def placeholder(kind: BackendKind) -> str:
    if kind == BackendKind.POSTGRES:
        return "%s"
    return "?"


def translate_sql(sql: str, kind: BackendKind) -> str:
    if kind == BackendKind.SQLITE:
        return sql
    return sql.replace("?", "%s")


def sql_requests_today_filter(kind: BackendKind) -> str:
    if kind == BackendKind.POSTGRES:
        return "created_at::date = CURRENT_DATE"
    return "date(created_at) = date('now')"


def insert_ignore_sql(
    table: str,
    conflict_columns: list[str],
    columns: list[str],
    kind: BackendKind,
) -> str:
    column_sql = ", ".join(columns)
    placeholder_sql = ", ".join(placeholder(kind) for _ in columns)
    if kind == BackendKind.SQLITE:
        return (
            f"INSERT OR IGNORE INTO {table} ({column_sql}) VALUES ({placeholder_sql})"
        )
    conflict_sql = ", ".join(conflict_columns)
    return (
        f"INSERT INTO {table} ({column_sql}) VALUES ({placeholder_sql}) "
        f"ON CONFLICT ({conflict_sql}) DO NOTHING"
    )