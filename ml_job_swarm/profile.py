from __future__ import annotations

import json
import sqlite3
from collections.abc import Mapping
from typing import Any


REQUIRED_PREFERENCE_IDS = ["role", "level", "location", "work_mode", "company_stage"]

_REQUIRED_PREFERENCE_ID_SET = set(REQUIRED_PREFERENCE_IDS)
_KEYWORD_COLUMNS = {
    "desired_titles": "desired_titles_json",
    "levels": "levels_json",
    "locations": "locations_json",
    "remote_modes": "remote_modes_json",
    "company_stages": "company_stages_json",
}


class ProfileAccessDenied(PermissionError):
    pass


def create_target_profile(
    conn: sqlite3.Connection,
    resume_asset_id: int,
    keywords: Mapping[str, Any],
    preferences: Mapping[str, Any],
    *,
    user_id: str | None = None,
) -> int:
    _require_resume_asset(conn, resume_asset_id)
    _validate_preferences(preferences)
    if not isinstance(keywords, Mapping):
        raise ValueError("keywords must be a mapping")

    values = _profile_column_values(keywords, preferences)
    name = _profile_name(keywords)

    with conn:
        cursor = conn.execute(
            """
            INSERT INTO target_profiles (
                user_id,
                resume_asset_id,
                name,
                version,
                desired_titles_json,
                levels_json,
                locations_json,
                remote_modes_json,
                company_stages_json,
                active
            )
            VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?, 1)
            """,
            (
                user_id,
                resume_asset_id,
                name,
                values["desired_titles_json"],
                values["levels_json"],
                values["locations_json"],
                values["remote_modes_json"],
                values["company_stages_json"],
            ),
        )
        target_profile_id = int(cursor.lastrowid)
        _replace_preference_answers(conn, target_profile_id, preferences)

    return target_profile_id


def update_preferences(
    conn: sqlite3.Connection,
    target_profile_id: int,
    preferences: Mapping[str, Any],
) -> int:
    _validate_preferences(preferences)
    current_version = current_profile_version(conn, target_profile_id)
    next_version = current_version + 1

    with conn:
        conn.execute(
            "DELETE FROM preference_answers WHERE target_profile_id = ?",
            (target_profile_id,),
        )
        _replace_preference_answers(conn, target_profile_id, preferences)
        conn.execute(
            """
            UPDATE target_profiles
            SET
                version = ?,
                desired_titles_json = ?,
                levels_json = ?,
                locations_json = ?,
                remote_modes_json = ?,
                company_stages_json = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                next_version,
                _preference_values(preferences, "role"),
                _preference_values(preferences, "level"),
                _preference_values(preferences, "location"),
                _preference_values(preferences, "work_mode"),
                _preference_values(preferences, "company_stage"),
                target_profile_id,
            ),
        )

    return next_version


def current_profile_version(conn: sqlite3.Connection, target_profile_id: int) -> int:
    row = conn.execute(
        "SELECT version FROM target_profiles WHERE id = ?",
        (target_profile_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"target_profile_id not found: {target_profile_id}")
    return int(_row_value(row, "version"))


def require_target_profile_access(
    conn: sqlite3.Connection,
    target_profile_id: int,
    *,
    user_id: str | None,
) -> None:
    if user_id is None:
        return
    row = conn.execute(
        "SELECT user_id FROM target_profiles WHERE id = ?",
        (target_profile_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"target_profile_id not found: {target_profile_id}")
    owner_id = _row_value(row, "user_id")
    if owner_id is not None and str(owner_id) != user_id:
        raise ProfileAccessDenied(f"target_profile_id not accessible: {target_profile_id}")


def _validate_preferences(preferences: Mapping[str, Any]) -> None:
    if not isinstance(preferences, Mapping):
        raise ValueError("preferences must be a mapping")

    preference_ids = set(preferences)
    missing = [key for key in REQUIRED_PREFERENCE_IDS if key not in preference_ids]
    extra = sorted(preference_ids - _REQUIRED_PREFERENCE_ID_SET)
    if not missing and not extra:
        return

    parts = []
    if missing:
        parts.append(f"missing preference ids: {', '.join(missing)}")
    if extra:
        parts.append(f"extra preference ids: {', '.join(extra)}")
    raise ValueError("; ".join(parts))


def _require_resume_asset(conn: sqlite3.Connection, resume_asset_id: int) -> None:
    row = conn.execute(
        "SELECT id FROM resume_assets WHERE id = ?",
        (resume_asset_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"resume_asset_id not found: {resume_asset_id}")


def _replace_preference_answers(
    conn: sqlite3.Connection,
    target_profile_id: int,
    preferences: Mapping[str, Any],
) -> None:
    conn.executemany(
        """
        INSERT INTO preference_answers (target_profile_id, question_key, answer_json)
        VALUES (?, ?, ?)
        """,
        [
            (
                target_profile_id,
                question_key,
                json.dumps(preferences[question_key], sort_keys=True),
            )
            for question_key in REQUIRED_PREFERENCE_IDS
        ],
    )


def _profile_column_values(
    keywords: Mapping[str, Any],
    preferences: Mapping[str, Any],
) -> dict[str, str]:
    values = {
        column: _to_json_list(keywords.get(keyword_key, []))
        for keyword_key, column in _KEYWORD_COLUMNS.items()
    }
    values["desired_titles_json"] = _preference_values(preferences, "role")
    values["levels_json"] = _preference_values(preferences, "level")
    values["locations_json"] = _preference_values(preferences, "location")
    values["remote_modes_json"] = _preference_values(preferences, "work_mode")
    values["company_stages_json"] = _preference_values(preferences, "company_stage")
    return values


def _preference_values(preferences: Mapping[str, Any], key: str) -> str:
    value = preferences[key]
    if isinstance(value, Mapping) and "answer" in value:
        value = value["answer"]
    return _to_json_list(value)


def _to_json_list(value: Any) -> str:
    if value is None:
        items: list[Any] = []
    elif isinstance(value, list):
        items = value
    elif isinstance(value, tuple):
        items = list(value)
    else:
        items = [value]
    return json.dumps(items, sort_keys=True)


def _profile_name(keywords: Mapping[str, Any]) -> str:
    titles = keywords.get("desired_titles", [])
    if isinstance(titles, (list, tuple)) and titles:
        return str(titles[0])
    if titles:
        return str(titles)
    return "Target profile"


def _row_value(row: Any, key: str) -> Any:
    try:
        return row[key]
    except (IndexError, TypeError):
        return row[0]
