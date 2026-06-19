from __future__ import annotations

import csv
import io
import json
import re
import sqlite3
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime

from ml_job_swarm.catalog import _normalize_name


_LINKEDIN_HEADER_MARKERS = ("First Name", "Last Name", "Company")
_COMPANY_STRIP = re.compile(
    r"\b(inc\.?|corp\.?|llc\.?|ltd\.?|co\.?|group|holdings|"
    r"technologies|tech|software|solutions|services|systems|labs?|ai)\b",
    re.IGNORECASE,
)
_NON_ALNUM = re.compile(r"[^a-z0-9 ]")
_WS = re.compile(r"\s+")


@dataclass(frozen=True)
class LinkedInConnection:
    first_name: str
    last_name: str
    profile_url: str
    company: str
    position: str
    connected_on: str

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()


@dataclass(frozen=True)
class LinkedInImportResult:
    import_id: int
    imported: int
    updated: int
    skipped: int


@dataclass(frozen=True)
class CompanyConnectionMatch:
    company_id: int
    company_name: str
    connections: tuple[dict[str, object], ...]


def parse_linkedin_connections_csv(text: str) -> list[LinkedInConnection]:
    lines = text.splitlines()
    header_index = -1
    headers: list[str] = []
    for index, line in enumerate(lines):
        if all(marker in line for marker in _LINKEDIN_HEADER_MARKERS):
            header_index = index
            headers = _parse_csv_line(line)
            break
    if header_index == -1:
        raise ValueError(
            "Could not find standard LinkedIn connection header row."
        )

    connections: list[LinkedInConnection] = []
    for line in lines[header_index + 1 :]:
        stripped = line.strip()
        if not stripped:
            continue
        values = _parse_csv_line(stripped)
        if len(values) < len(headers):
            continue
        row = {
            header.strip().strip('"'): (
                values[index].strip().strip('"') if index < len(values) else ""
            )
            for index, header in enumerate(headers)
        }
        first_name = row.get("First Name", "").strip()
        last_name = row.get("Last Name", "").strip()
        profile_url = row.get("URL", "").strip()
        if not first_name and not last_name:
            continue
        connections.append(
            LinkedInConnection(
                first_name=first_name,
                last_name=last_name,
                profile_url=profile_url,
                company=(row.get("Company") or "").strip(),
                position=(row.get("Position") or "").strip(),
                connected_on=(row.get("Connected On") or "").strip(),
            )
        )
    if not connections:
        raise ValueError("No parsed LinkedIn connections found.")
    return connections


def normalize_connection_company(name: str) -> str:
    text = unicodedata.normalize("NFKD", name or "")
    text = text.encode("ascii", "ignore").decode().casefold()
    text = _COMPANY_STRIP.sub("", text)
    text = _NON_ALNUM.sub(" ", text)
    return _WS.sub(" ", text).strip()


def _storage_user_id(user_id: str | None) -> str:
    return user_id or ""


def _append_user_scope(
    clauses: list[str],
    params: list[object],
    *,
    user_id: str | None,
) -> None:
    if user_id is not None:
        clauses.append("user_id = ?")
        params.append(user_id)


def import_linkedin_connections(
    conn: sqlite3.Connection,
    *,
    connections: list[LinkedInConnection],
    filename: str = "",
    user_id: str | None = None,
) -> LinkedInImportResult:
    now = datetime.now(UTC).isoformat()
    scoped_user_id = _storage_user_id(user_id)
    with conn:
        cursor = conn.execute(
            """
            INSERT INTO linkedin_connection_imports (
              user_id,
              filename,
              connection_count
            )
            VALUES (?, ?, ?)
            """,
            (scoped_user_id, filename, len(connections)),
        )
        import_id = int(cursor.lastrowid)
        imported = 0
        updated = 0
        skipped = 0
        for connection in connections:
            if not connection.profile_url:
                skipped += 1
                continue
            company_norm = normalize_connection_company(connection.company)
            existing = conn.execute(
                """
                SELECT id
                FROM linkedin_connections
                WHERE profile_url = ? AND user_id = ?
                """,
                (connection.profile_url, scoped_user_id),
            ).fetchone()
            conn.execute(
                """
                INSERT INTO linkedin_connections (
                  user_id,
                  profile_url,
                  first_name,
                  last_name,
                  company,
                  company_norm,
                  position,
                  connected_on,
                  import_id,
                  updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, profile_url) DO UPDATE SET
                  first_name = excluded.first_name,
                  last_name = excluded.last_name,
                  company = excluded.company,
                  company_norm = excluded.company_norm,
                  position = excluded.position,
                  connected_on = excluded.connected_on,
                  import_id = excluded.import_id,
                  updated_at = excluded.updated_at
                """,
                (
                    scoped_user_id,
                    connection.profile_url,
                    connection.first_name,
                    connection.last_name,
                    connection.company,
                    company_norm,
                    connection.position,
                    connection.connected_on,
                    import_id,
                    now,
                ),
            )
            if existing:
                updated += 1
            else:
                imported += 1
    return LinkedInImportResult(
        import_id=import_id,
        imported=imported,
        updated=updated,
        skipped=skipped,
    )


def linkedin_connection_count(
    conn: sqlite3.Connection,
    *,
    user_id: str | None = None,
) -> int:
    clauses: list[str] = []
    params: list[object] = []
    _append_user_scope(clauses, params, user_id=user_id)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    row = conn.execute(
        f"SELECT COUNT(*) AS count FROM linkedin_connections{where}",
        params,
    ).fetchone()
    return int(row["count"] if row else 0)


def latest_import_summary(
    conn: sqlite3.Connection,
    *,
    user_id: str | None = None,
) -> dict[str, object] | None:
    clauses: list[str] = []
    params: list[object] = []
    _append_user_scope(clauses, params, user_id=user_id)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    row = conn.execute(
        f"""
        SELECT id, filename, connection_count, created_at
        FROM linkedin_connection_imports
        {where}
        ORDER BY id DESC
        LIMIT 1
        """,
        params,
    ).fetchone()
    return dict(row) if row else None


def list_linkedin_connections(
    conn: sqlite3.Connection,
    *,
    search: str = "",
    user_id: str | None = None,
) -> list[dict[str, object]]:
    clauses: list[str] = []
    params: list[object] = []
    _append_user_scope(clauses, params, user_id=user_id)
    if search.strip():
        needle = f"%{search.strip().casefold()}%"
        clauses.append(
            """
            (
              lower(first_name || ' ' || last_name) LIKE ?
              OR lower(company) LIKE ?
              OR lower(position) LIKE ?
            )
            """
        )
        params.extend([needle, needle, needle])
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    query = f"""
        SELECT
          id,
          profile_url,
          first_name,
          last_name,
          company,
          company_norm,
          position,
          connected_on
        FROM linkedin_connections
        {where}
        ORDER BY company, last_name, first_name, id
    """
    return [dict(row) for row in conn.execute(query, params).fetchall()]


def grouped_connections_by_company(
    conn: sqlite3.Connection,
    *,
    search: str = "",
    user_id: str | None = None,
) -> list[dict[str, object]]:
    grouped: dict[str, dict[str, object]] = {}
    for row in list_linkedin_connections(conn, search=search, user_id=user_id):
        company = str(row.get("company") or "Not specified / freelance")
        bucket = grouped.setdefault(
            company,
            {"company": company, "connections": []},
        )
        bucket["connections"].append(row)
    companies = list(grouped.values())
    companies.sort(
        key=lambda item: (-len(item["connections"]), str(item["company"]).casefold())
    )
    return companies


def _catalog_company_terms(
    conn: sqlite3.Connection,
) -> list[dict[str, object]]:
    rows = conn.execute(
        """
        SELECT id, name, normalized_name, aliases_json
        FROM companies
        ORDER BY name
        """
    ).fetchall()
    terms: list[dict[str, object]] = []
    for row in rows:
        aliases = json.loads(row["aliases_json"] or "[]")
        normalized_terms = {
            _normalize_name(row["name"]),
            normalize_connection_company(row["name"]),
            row["normalized_name"],
        }
        for alias in aliases:
            normalized_terms.add(_normalize_name(str(alias)))
            normalized_terms.add(normalize_connection_company(str(alias)))
        normalized_terms.discard("")
        terms.append(
            {
                "company_id": int(row["id"]),
                "company_name": row["name"],
                "terms": tuple(sorted(normalized_terms)),
            }
        )
    return terms


def _norm_contains(haystack: str, needle: str) -> bool:
    if not haystack or not needle or len(needle) < 3:
        return False
    return re.search(rf"(^| ){re.escape(needle)}( |$)", haystack) is not None


def connection_matches_company(
    connection_company_norm: str,
    *,
    company_terms: tuple[str, ...],
) -> bool:
    if not connection_company_norm:
        return False
    for term in company_terms:
        if not term:
            continue
        if connection_company_norm == term or term == connection_company_norm:
            return True
        if _norm_contains(connection_company_norm, term) or _norm_contains(
            term, connection_company_norm
        ):
            return True
    return False


def connections_for_company_id(
    conn: sqlite3.Connection,
    company_id: int,
    *,
    user_id: str | None = None,
) -> list[dict[str, object]]:
    catalog = _catalog_company_terms(conn)
    company = next(
        (item for item in catalog if int(item["company_id"]) == company_id),
        None,
    )
    if company is None:
        return []
    return _connections_matching_terms(
        conn,
        company_terms=company["terms"],
        user_id=user_id,
    )


def connections_for_company_ids(
    conn: sqlite3.Connection,
    company_ids: list[int],
    *,
    user_id: str | None = None,
) -> dict[int, list[dict[str, object]]]:
    if not company_ids:
        return {}
    catalog = {
        int(item["company_id"]): item
        for item in _catalog_company_terms(conn)
        if int(item["company_id"]) in company_ids
    }
    all_connections = list_linkedin_connections(conn, user_id=user_id)
    grouped: dict[int, list[dict[str, object]]] = {
        company_id: [] for company_id in company_ids
    }
    for row in all_connections:
        company_norm = str(row.get("company_norm") or "")
        for company_id, company in catalog.items():
            if connection_matches_company(
                company_norm,
                company_terms=company["terms"],
            ):
                grouped[company_id].append(row)
    for company_id in grouped:
        grouped[company_id].sort(
            key=lambda row: (
                str(row.get("last_name") or ""),
                str(row.get("first_name") or ""),
            )
        )
    return grouped


def matched_catalog_companies(
    conn: sqlite3.Connection,
    *,
    user_id: str | None = None,
) -> list[CompanyConnectionMatch]:
    catalog = _catalog_company_terms(conn)
    all_connections = list_linkedin_connections(conn, user_id=user_id)
    matches: list[CompanyConnectionMatch] = []
    for company in catalog:
        matched = [
            row
            for row in all_connections
            if connection_matches_company(
                str(row.get("company_norm") or ""),
                company_terms=company["terms"],
            )
        ]
        if not matched:
            continue
        matches.append(
            CompanyConnectionMatch(
                company_id=int(company["company_id"]),
                company_name=str(company["company_name"]),
                connections=tuple(matched),
            )
        )
    matches.sort(key=lambda item: (-len(item.connections), item.company_name.casefold()))
    return matches


def _connections_matching_terms(
    conn: sqlite3.Connection,
    *,
    company_terms: tuple[str, ...],
    user_id: str | None = None,
) -> list[dict[str, object]]:
    rows = [
        row
        for row in list_linkedin_connections(conn, user_id=user_id)
        if connection_matches_company(
            str(row.get("company_norm") or ""),
            company_terms=company_terms,
        )
    ]
    rows.sort(
        key=lambda row: (
            str(row.get("last_name") or ""),
            str(row.get("first_name") or ""),
        )
    )
    return rows


def _parse_csv_line(line: str) -> list[str]:
    return next(csv.reader(io.StringIO(line)))