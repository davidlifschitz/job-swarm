from __future__ import annotations


def csv_safe_value(value: object) -> object:
    if not isinstance(value, str):
        return value
    if value and value[0] in {"=", "+", "-", "@", "\t", "\r"}:
        return f"'{value}"
    return value


def csv_safe_row(row: dict[str, object]) -> dict[str, object]:
    return {key: csv_safe_value(value) for key, value in row.items()}
