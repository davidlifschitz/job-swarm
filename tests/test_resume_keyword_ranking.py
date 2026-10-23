import os

import pytest

from ml_job_swarm.filtering import _resume_keywords
from ml_job_swarm.store import connect, init_db


@pytest.fixture(params=["sqlite", "postgres"])
def keyword_conn(request):
    if request.param == "postgres":
        database_url = os.environ.get("ML_JOB_SWARM_TEST_DATABASE_URL", "")
        if not database_url:
            pytest.skip("Set ML_JOB_SWARM_TEST_DATABASE_URL to run Postgres keyword tests")
        from ml_job_swarm.db.postgres_backend import connect_postgres

        conn = connect_postgres(database_url)
    else:
        conn = connect()
    init_db(conn)
    try:
        yield conn
    finally:
        conn.rollback()
        conn.close()


def _resume_asset(conn, digest):
    return conn.execute(
        """
        INSERT INTO resume_assets (original_filename, content_type, storage_path, sha256)
        VALUES ('keywords.pdf', 'application/pdf', '/tmp/keywords.pdf', ?)
        """,
        (digest,),
    ).lastrowid


def _parse_keywords(conn, asset_id, keywords):
    parse_id = conn.execute(
        """
        INSERT INTO resume_parse_runs
          (resume_asset_id, parser, parser_version, status, confidence)
        VALUES (?, 'test', '1', 'parsed', 1.0)
        """,
        (asset_id,),
    ).lastrowid
    for keyword, weight in keywords:
        conn.execute(
            "INSERT INTO resume_keywords (parse_run_id, keyword, weight) VALUES (?, ?, ?)",
            (parse_id, keyword, weight),
        )


def test_resume_keywords_deduplicate_by_highest_weight_with_stable_ties(keyword_conn):
    asset_id = _resume_asset(keyword_conn, "keyword-ranking-resume")
    _parse_keywords(keyword_conn, asset_id, [("python", 0.2), ("sql", 2.0)])
    _parse_keywords(
        keyword_conn, asset_id, [("python", 5.0), ("rust", 2.0), ("llm", 0.1)],
    )
    other_asset_id = _resume_asset(keyword_conn, "other-keyword-ranking-resume")
    _parse_keywords(keyword_conn, other_asset_id, [("unrelated", 100.0)])

    assert _resume_keywords(keyword_conn, asset_id) == ["python", "rust", "sql", "llm"]


def test_resume_keywords_empty_for_unparsed_resume(keyword_conn):
    asset_id = _resume_asset(keyword_conn, "unparsed-keyword-ranking-resume")

    assert _resume_keywords(keyword_conn, asset_id) == []
