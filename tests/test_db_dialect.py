from ml_job_swarm.db.dialect import (
    BackendKind,
    insert_ignore_sql,
    placeholder,
    translate_sql,
)


def test_placeholder_sqlite_uses_question_mark():
    assert placeholder(BackendKind.SQLITE) == "?"
    assert translate_sql("SELECT ? AS value", BackendKind.SQLITE) == "SELECT ? AS value"


def test_placeholder_postgres_uses_percent_s():
    assert placeholder(BackendKind.POSTGRES) == "%s"
    assert translate_sql("SELECT ? AS value", BackendKind.POSTGRES) == "SELECT %s AS value"


def test_insert_ignore_sql_differs_by_backend():
    sqlite_sql = insert_ignore_sql(
        "resume_assets",
        ["user_id", "sha256"],
        ["original_filename"],
        BackendKind.SQLITE,
    )
    postgres_sql = insert_ignore_sql(
        "resume_assets",
        ["user_id", "sha256"],
        ["original_filename"],
        BackendKind.POSTGRES,
    )
    assert "INSERT OR IGNORE" in sqlite_sql
    assert "ON CONFLICT" in postgres_sql
    assert "DO NOTHING" in postgres_sql