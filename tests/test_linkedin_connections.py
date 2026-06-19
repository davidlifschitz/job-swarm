from pathlib import Path

import pytest

from ml_job_swarm.linkedin_connections import (
    connection_matches_company,
    connections_for_company_id,
    import_linkedin_connections,
    linkedin_connection_count,
    matched_catalog_companies,
    normalize_connection_company,
    parse_linkedin_connections_csv,
)
from ml_job_swarm.store import connect, init_db

FIXTURE_CSV = Path(__file__).parent / "fixtures" / "linkedin_connections.csv"


def test_parse_linkedin_connections_csv_reads_standard_export():
    text = FIXTURE_CSV.read_text()
    connections = parse_linkedin_connections_csv(text)

    assert len(connections) == 3
    assert connections[0].full_name == "Jamie Example"
    assert connections[0].company == "Dataiku"
    assert connections[0].position == "Technical Talent Acquisition Partner"


def test_parse_linkedin_connections_csv_rejects_missing_header():
    with pytest.raises(ValueError, match="header row"):
        parse_linkedin_connections_csv("name,title\nAlice,Engineer")


def test_normalize_connection_company_strips_common_suffixes():
    assert normalize_connection_company("Dataiku Inc.") == "dataiku"
    assert normalize_connection_company("Cross River Bank") == "cross river bank"


def test_import_and_match_connections_to_catalog_companies():
    conn = connect()
    init_db(conn)
    conn.execute(
        """
        INSERT INTO companies (name, normalized_name, aliases_json)
        VALUES (?, ?, ?)
        """,
        ("Dataiku", "dataiku", "[]"),
    )
    conn.execute(
        """
        INSERT INTO companies (name, normalized_name, aliases_json)
        VALUES (?, ?, ?)
        """,
        ("Cross River", "cross river", "[]"),
    )
    dataiku_id = conn.execute(
        "SELECT id FROM companies WHERE name = 'Dataiku'"
    ).fetchone()["id"]
    cross_river_id = conn.execute(
        "SELECT id FROM companies WHERE name = 'Cross River'"
    ).fetchone()["id"]

    connections = parse_linkedin_connections_csv(FIXTURE_CSV.read_text())
    result = import_linkedin_connections(
        conn,
        connections=connections,
        filename="Connections.csv",
    )

    assert result.imported == 3
    assert linkedin_connection_count(conn) == 3
    assert len(connections_for_company_id(conn, dataiku_id)) == 1
    assert len(connections_for_company_id(conn, cross_river_id)) == 1
    matches = matched_catalog_companies(conn)
    assert {match.company_name for match in matches} == {"Dataiku", "Cross River"}


def test_connection_matches_company_supports_alias_terms():
    assert connection_matches_company(
        normalize_connection_company("DeepMind"),
        company_terms=("google deepmind", "deepmind"),
    )


def test_connection_matches_company_supports_jpmorgan_alias_variants():
    terms = (
        "jpmorgan chase",
        "jpmorganchase",
        "j p morgan",
        "jpmorgan chase co",
        "jp morgan",
    )
    for company in (
        "JPMorganChase",
        "JPMorgan Chase & Co.",
        "J.P. Morgan",
    ):
        assert connection_matches_company(
            normalize_connection_company(company),
            company_terms=terms,
        )


def test_import_is_idempotent_on_profile_url():
    conn = connect()
    init_db(conn)
    connections = parse_linkedin_connections_csv(FIXTURE_CSV.read_text())
    first = import_linkedin_connections(conn, connections=connections)
    second = import_linkedin_connections(conn, connections=connections)

    assert first.imported == 3
    assert second.updated == 3
    assert second.imported == 0
    assert linkedin_connection_count(conn) == 3