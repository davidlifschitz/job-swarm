import sqlite3
from typing import get_args

import pytest

from ml_job_swarm import models
from ml_job_swarm.store import connect, init_db, table_columns


EXPECTED_TABLES = {
    "companies",
    "job_sources",
    "company_source_review_queue",
    "ingestion_runs",
    "source_friction_events",
    "admin_audit_events",
    "cloud_runs",
    "cloud_run_events",
    "job_snapshots",
    "jobs",
    "resume_assets",
    "resume_parse_runs",
    "resume_sections",
    "resume_keywords",
    "target_profiles",
    "preference_answers",
    "resume_rewrite_suggestions",
    "rules_filter_results",
    "fit_reviews",
    "llm_requests",
    "job_decisions",
    "application_packets",
    "contacts",
    "referral_contacts",
    "linkedin_connection_imports",
    "linkedin_connections",
}


def test_init_db_creates_foundation_tables():
    conn = connect()

    init_db(conn)

    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'"
    ).fetchall()
    table_names = {row["name"] for row in rows}
    assert EXPECTED_TABLES <= table_names


def test_schema_includes_privacy_and_review_gate_fields():
    conn = connect()
    init_db(conn)

    assert {
        "parser",
        "parser_version",
        "status",
        "confidence",
        "vision_fallback_status",
        "vision_fallback_consented_at",
    } <= table_columns(conn, "resume_parse_runs")
    assert {"version", "resume_asset_id", "active"} <= table_columns(
        conn, "target_profiles"
    )
    assert {"user_id", "sha256", "storage_path"} <= table_columns(conn, "resume_assets")
    assert {
        "fit_score",
        "label",
        "reasons_json",
        "risks_json",
        "recommendation",
        "profile_version",
    } <= table_columns(conn, "fit_reviews")
    assert {
        "provider",
        "model",
        "feature",
        "schema_version",
        "status",
        "request_hash",
        "response_json",
    } <= table_columns(conn, "llm_requests")
    assert {
        "job_id",
        "target_profile_id",
        "status",
        "packet_json",
        "checklist_json",
        "manual_submit_url",
    } <= table_columns(conn, "application_packets")
    assert {"jobs_closed"} <= table_columns(conn, "ingestion_runs")
    assert {
        "name",
        "email",
        "title",
        "notes",
    } <= table_columns(conn, "contacts")
    assert {
        "company_id",
        "contact_id",
        "relationship",
    } <= table_columns(conn, "referral_contacts")


def test_schema_tracks_admin_and_user_source_review_actions():
    conn = connect()
    init_db(conn)

    assert {
        "company_name",
        "requested_url",
        "reason",
        "status",
        "reviewed_at",
        "reviewed_by",
    } <= table_columns(conn, "company_source_review_queue")
    assert {
        "actor",
        "action",
        "target_type",
        "target_id",
        "before_json",
        "after_json",
    } <= table_columns(conn, "admin_audit_events")
    assert {
        "event_type",
        "url",
        "status_code",
        "details_json",
        "review_status",
        "reviewed_at",
        "reviewed_by",
        "review_note",
    } <= table_columns(conn, "source_friction_events")


def test_schema_tracks_local_job_decisions_by_profile():
    conn = connect()
    init_db(conn)

    assert {
        "job_id",
        "target_profile_id",
        "decision",
        "notes",
        "created_at",
        "updated_at",
    } <= table_columns(conn, "job_decisions")


def test_llm_request_schema_does_not_store_raw_private_prompts():
    conn = connect()
    init_db(conn)

    forbidden_columns = {
        "prompt",
        "raw_prompt",
        "resume_text",
        "private_prompt",
        "request_body",
    }
    assert forbidden_columns.isdisjoint(table_columns(conn, "llm_requests"))


def test_store_helpers_are_safe_and_idempotent():
    conn = connect()
    init_db(conn)
    init_db(conn)

    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    row = conn.execute("SELECT name FROM sqlite_master LIMIT 1").fetchone()
    assert row["name"]

    with pytest.raises(ValueError):
        table_columns(conn, "jobs; DROP TABLE jobs")


def test_foreign_key_constraints_are_enforced():
    conn = connect()
    init_db(conn)

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            """
            INSERT INTO jobs (company_id, title, source_url, content_hash)
            VALUES (999, 'Missing Company Role', 'https://example.com', 'abc')
            """
        )


def test_foundation_domain_values_match_spec():
    assert set(get_args(models.PolicyMode)) == {"allowed", "blocked", "manual_link"}
    assert set(get_args(models.FitLabel)) == {
        "Strong fit",
        "Possible fit",
        "Mismatch risk",
        "Filtered out",
    }
    assert set(get_args(models.RulesOutcome)) == {"pass", "soft_pass", "reject"}
    assert set(get_args(models.FrictionEventType)) == {
        "policy_blocked",
        "captcha_or_login",
        "rate_limited",
        "blocked_response",
        "layout_changed",
        "empty_suspicious",
        "manual_review_needed",
        "timeout",
    }
    assert set(get_args(models.JobDecision)) == {"saved", "hidden"}
