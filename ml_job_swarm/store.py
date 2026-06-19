from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ml_job_swarm.db.protocol import Database
    from ml_job_swarm.db.sqlite_backend import SQLiteDatabase


SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS companies (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  normalized_name TEXT NOT NULL UNIQUE,
  aliases_json TEXT NOT NULL DEFAULT '[]',
  categories_json TEXT NOT NULL DEFAULT '[]',
  stage TEXT,
  priority_tier INTEGER NOT NULL DEFAULT 3,
  careers_url TEXT,
  ats_type TEXT,
  source_quality TEXT NOT NULL DEFAULT 'unreviewed',
  is_active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS job_sources (
  id INTEGER PRIMARY KEY,
  company_id INTEGER REFERENCES companies(id) ON DELETE CASCADE,
  url TEXT NOT NULL,
  source_type TEXT NOT NULL DEFAULT 'careers',
  policy_mode TEXT NOT NULL DEFAULT 'allowed',
  review_status TEXT NOT NULL DEFAULT 'pending',
  last_checked_at TEXT,
  disabled_at TEXT,
  notes TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(company_id, url)
);

CREATE TABLE IF NOT EXISTS company_source_review_queue (
  id INTEGER PRIMARY KEY,
  company_name TEXT NOT NULL,
  requested_url TEXT,
  reason TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending',
  reviewed_at TEXT,
  reviewed_by TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ingestion_runs (
  id INTEGER PRIMARY KEY,
  started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  finished_at TEXT,
  status TEXT NOT NULL DEFAULT 'running',
  source_count INTEGER NOT NULL DEFAULT 0,
  jobs_seen INTEGER NOT NULL DEFAULT 0,
  jobs_added INTEGER NOT NULL DEFAULT 0,
  jobs_updated INTEGER NOT NULL DEFAULT 0,
  jobs_closed INTEGER NOT NULL DEFAULT 0,
  error TEXT
);

CREATE TABLE IF NOT EXISTS source_friction_events (
  id INTEGER PRIMARY KEY,
  job_source_id INTEGER REFERENCES job_sources(id) ON DELETE SET NULL,
  ingestion_run_id INTEGER REFERENCES ingestion_runs(id) ON DELETE SET NULL,
  event_type TEXT NOT NULL,
  url TEXT NOT NULL,
  status_code INTEGER,
  details_json TEXT NOT NULL DEFAULT '{}',
  review_status TEXT NOT NULL DEFAULT 'unreviewed',
  reviewed_at TEXT,
  reviewed_by TEXT,
  review_note TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS admin_audit_events (
  id INTEGER PRIMARY KEY,
  actor TEXT NOT NULL DEFAULT 'local-admin',
  action TEXT NOT NULL,
  target_type TEXT NOT NULL,
  target_id TEXT NOT NULL,
  before_json TEXT NOT NULL DEFAULT '{}',
  after_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS cloud_runs (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  requested_action TEXT NOT NULL,
  status TEXT NOT NULL,
  current_stage TEXT NOT NULL,
  input_manifest_json TEXT NOT NULL,
  output_manifest_json TEXT NOT NULL DEFAULT '{}',
  idempotency_key TEXT,
  trace_id TEXT NOT NULL UNIQUE,
  code_version TEXT NOT NULL DEFAULT 'unknown',
  container_image_digest TEXT NOT NULL DEFAULT 'unknown',
  dependency_lock_hash TEXT NOT NULL DEFAULT 'unknown',
  environment_class TEXT NOT NULL DEFAULT 'local',
  feature_flags_json TEXT NOT NULL DEFAULT '{}',
  source_policy_version TEXT NOT NULL,
  next_action TEXT,
  error_code TEXT,
  error_message TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  started_at TEXT,
  completed_at TEXT,
  last_heartbeat_at TEXT,
  cancel_requested_at TEXT,
  UNIQUE(user_id, idempotency_key)
);

CREATE TABLE IF NOT EXISTS cloud_run_events (
  id INTEGER PRIMARY KEY,
  run_id TEXT NOT NULL REFERENCES cloud_runs(id) ON DELETE CASCADE,
  event_type TEXT NOT NULL,
  status TEXT NOT NULL,
  stage TEXT NOT NULL,
  message TEXT NOT NULL,
  payload_json TEXT NOT NULL DEFAULT '{}',
  trace_id TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS job_snapshots (
  id INTEGER PRIMARY KEY,
  ingestion_run_id INTEGER REFERENCES ingestion_runs(id) ON DELETE CASCADE,
  job_source_id INTEGER REFERENCES job_sources(id) ON DELETE SET NULL,
  external_id TEXT,
  title TEXT NOT NULL,
  company_name TEXT NOT NULL,
  location_text TEXT,
  remote_mode TEXT,
  raw_json TEXT NOT NULL DEFAULT '{}',
  content_hash TEXT NOT NULL,
  captured_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS jobs (
  id INTEGER PRIMARY KEY,
  company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
  job_source_id INTEGER REFERENCES job_sources(id) ON DELETE SET NULL,
  external_id TEXT,
  title TEXT NOT NULL,
  department TEXT,
  location_text TEXT,
  remote_mode TEXT,
  employment_type TEXT,
  seniority TEXT,
  description_text TEXT,
  requirements_text TEXT,
  apply_url TEXT,
  source_url TEXT NOT NULL,
  content_hash TEXT NOT NULL,
  first_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  status TEXT NOT NULL DEFAULT 'open',
  UNIQUE(company_id, external_id)
);

CREATE TABLE IF NOT EXISTS resume_assets (
  id INTEGER PRIMARY KEY,
  user_id TEXT,
  original_filename TEXT NOT NULL,
  content_type TEXT NOT NULL,
  storage_path TEXT NOT NULL,
  sha256 TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(user_id, sha256)
);

CREATE TABLE IF NOT EXISTS resume_parse_runs (
  id INTEGER PRIMARY KEY,
  resume_asset_id INTEGER NOT NULL REFERENCES resume_assets(id) ON DELETE CASCADE,
  parser TEXT NOT NULL,
  parser_version TEXT NOT NULL,
  status TEXT NOT NULL,
  confidence REAL NOT NULL,
  vision_fallback_status TEXT NOT NULL DEFAULT 'not_needed',
  vision_fallback_consented_at TEXT,
  error TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS resume_sections (
  id INTEGER PRIMARY KEY,
  parse_run_id INTEGER NOT NULL REFERENCES resume_parse_runs(id) ON DELETE CASCADE,
  section_type TEXT NOT NULL,
  heading TEXT,
  text TEXT NOT NULL,
  sort_order INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS resume_keywords (
  id INTEGER PRIMARY KEY,
  parse_run_id INTEGER NOT NULL REFERENCES resume_parse_runs(id) ON DELETE CASCADE,
  keyword TEXT NOT NULL,
  source_section TEXT,
  weight REAL NOT NULL DEFAULT 1.0
);

CREATE TABLE IF NOT EXISTS target_profiles (
  id INTEGER PRIMARY KEY,
  user_id TEXT,
  resume_asset_id INTEGER REFERENCES resume_assets(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  version INTEGER NOT NULL DEFAULT 1,
  desired_titles_json TEXT NOT NULL DEFAULT '[]',
  levels_json TEXT NOT NULL DEFAULT '[]',
  locations_json TEXT NOT NULL DEFAULT '[]',
  remote_modes_json TEXT NOT NULL DEFAULT '[]',
  company_stages_json TEXT NOT NULL DEFAULT '[]',
  active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS preference_answers (
  id INTEGER PRIMARY KEY,
  target_profile_id INTEGER NOT NULL REFERENCES target_profiles(id) ON DELETE CASCADE,
  question_key TEXT NOT NULL,
  answer_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS resume_rewrite_suggestions (
  id INTEGER PRIMARY KEY,
  resume_asset_id INTEGER NOT NULL REFERENCES resume_assets(id) ON DELETE CASCADE,
  job_id INTEGER REFERENCES jobs(id) ON DELETE CASCADE,
  target_profile_id INTEGER REFERENCES target_profiles(id) ON DELETE CASCADE,
  section_id INTEGER REFERENCES resume_sections(id) ON DELETE SET NULL,
  llm_request_id INTEGER REFERENCES llm_requests(id) ON DELETE SET NULL,
  suggestion_text TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'draft',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS rules_filter_results (
  id INTEGER PRIMARY KEY,
  job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
  target_profile_id INTEGER NOT NULL REFERENCES target_profiles(id) ON DELETE CASCADE,
  outcome TEXT NOT NULL,
  score INTEGER NOT NULL,
  reasons_json TEXT NOT NULL DEFAULT '[]',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS fit_reviews (
  id INTEGER PRIMARY KEY,
  job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
  target_profile_id INTEGER NOT NULL REFERENCES target_profiles(id) ON DELETE CASCADE,
  rules_filter_result_id INTEGER REFERENCES rules_filter_results(id) ON DELETE SET NULL,
  llm_request_id INTEGER REFERENCES llm_requests(id) ON DELETE SET NULL,
  fit_score INTEGER NOT NULL,
  label TEXT NOT NULL,
  reasons_json TEXT NOT NULL DEFAULT '[]',
  risks_json TEXT NOT NULL DEFAULT '[]',
  recommendation TEXT NOT NULL,
  profile_version INTEGER NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS job_decisions (
  id INTEGER PRIMARY KEY,
  job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
  target_profile_id INTEGER NOT NULL REFERENCES target_profiles(id) ON DELETE CASCADE,
  decision TEXT NOT NULL CHECK (decision IN ('saved', 'hidden')),
  notes TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(job_id, target_profile_id)
);

CREATE TABLE IF NOT EXISTS application_packets (
  id INTEGER PRIMARY KEY,
  job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
  target_profile_id INTEGER NOT NULL REFERENCES target_profiles(id) ON DELETE CASCADE,
  status TEXT NOT NULL DEFAULT 'prepared' CHECK (status IN ('prepared', 'submitted')),
  packet_json TEXT NOT NULL DEFAULT '{}',
  checklist_json TEXT NOT NULL DEFAULT '[]',
  manual_submit_url TEXT NOT NULL DEFAULT '',
  notes TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(job_id, target_profile_id)
);

CREATE TABLE IF NOT EXISTS contacts (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  email TEXT NOT NULL DEFAULT '',
  title TEXT NOT NULL DEFAULT '',
  notes TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS referral_contacts (
  id INTEGER PRIMARY KEY,
  company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
  contact_id INTEGER NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
  relationship TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(company_id, contact_id)
);

CREATE TABLE IF NOT EXISTS linkedin_connection_imports (
  id INTEGER PRIMARY KEY,
  user_id TEXT,
  filename TEXT NOT NULL DEFAULT '',
  connection_count INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS linkedin_connections (
  id INTEGER PRIMARY KEY,
  user_id TEXT,
  profile_url TEXT NOT NULL,
  first_name TEXT NOT NULL DEFAULT '',
  last_name TEXT NOT NULL DEFAULT '',
  company TEXT NOT NULL DEFAULT '',
  company_norm TEXT NOT NULL DEFAULT '',
  position TEXT NOT NULL DEFAULT '',
  connected_on TEXT NOT NULL DEFAULT '',
  import_id INTEGER REFERENCES linkedin_connection_imports(id) ON DELETE SET NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(user_id, profile_url)
);

CREATE INDEX IF NOT EXISTS idx_linkedin_connections_company_norm
ON linkedin_connections(company_norm);

CREATE TABLE IF NOT EXISTS llm_requests (
  id INTEGER PRIMARY KEY,
  provider TEXT NOT NULL DEFAULT 'openrouter',
  model TEXT NOT NULL,
  feature TEXT NOT NULL,
  schema_version TEXT NOT NULL,
  status TEXT NOT NULL,
  request_hash TEXT NOT NULL,
  response_json TEXT NOT NULL DEFAULT '{}',
  error TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


def connect(
    path: str | Path = ":memory:", *, check_same_thread: bool = True
) -> sqlite3.Connection:
    from ml_job_swarm.db.sqlite_backend import connect_sqlite

    return connect_sqlite(path, check_same_thread=check_same_thread).native


def open_store_connection(
    *,
    db_path: str | Path = "jobs.db",
    check_same_thread: bool = True,
) -> "Database | sqlite3.Connection":
    from ml_job_swarm.db.dialect import BackendKind
    from ml_job_swarm.db.factory import backend_kind_from_env, connect_from_env

    if backend_kind_from_env() == BackendKind.POSTGRES:
        return connect_from_env(check_same_thread=check_same_thread)
    return connect(db_path, check_same_thread=check_same_thread)


def store_connection_label(
    *,
    db_path: str | Path = "jobs.db",
    env: dict[str, str] | None = None,
) -> str:
    import os

    source = env if env is not None else os.environ
    database_url = (source.get("DATABASE_URL") or "").strip()
    if database_url:
        return "postgresql://***"
    return str(db_path)


def _require_sqlite_connection(
    conn: sqlite3.Connection | "Database",
) -> sqlite3.Connection:
    from ml_job_swarm.db.postgres_backend import PostgresDatabase
    from ml_job_swarm.db.sqlite_backend import SQLiteDatabase

    if isinstance(conn, SQLiteDatabase):
        return conn.native
    if isinstance(conn, PostgresDatabase):
        raise NotImplementedError("Postgres schema init is implemented in Phase B1 migrations")
    if isinstance(conn, sqlite3.Connection):
        return conn
    raise TypeError(f"Unsupported database connection type: {type(conn)!r}")


def init_db(conn: sqlite3.Connection | "Database") -> None:
    from ml_job_swarm.db.postgres_backend import PostgresDatabase

    if isinstance(conn, PostgresDatabase):
        from ml_job_swarm.db.postgres_schema import apply_postgres_schema

        apply_postgres_schema(conn)
        return

    conn = _require_sqlite_connection(conn)
    conn.executescript(SCHEMA_SQL)
    _ensure_column(
        conn,
        "resume_rewrite_suggestions",
        "llm_request_id",
        "INTEGER REFERENCES llm_requests(id) ON DELETE SET NULL",
    )
    _ensure_column(
        conn,
        "ingestion_runs",
        "jobs_closed",
        "INTEGER NOT NULL DEFAULT 0",
    )
    _ensure_column(conn, "target_profiles", "user_id", "TEXT")
    _migrate_linkedin_connections_user_scope(conn)
    _migrate_resume_assets_user_scope(conn)
    conn.commit()


def _migrate_linkedin_connections_user_scope(conn: sqlite3.Connection) -> None:
    _ensure_column(conn, "linkedin_connection_imports", "user_id", "TEXT")
    _ensure_column(conn, "linkedin_connections", "user_id", "TEXT")
    row = conn.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table' AND name = 'linkedin_connections'
          AND sql LIKE '%UNIQUE(user_id, profile_url)%'
        """
    ).fetchone()
    if row is not None:
        return
    conn.executescript(
        """
        CREATE TABLE linkedin_connections__scoped (
          id INTEGER PRIMARY KEY,
          user_id TEXT,
          profile_url TEXT NOT NULL,
          first_name TEXT NOT NULL DEFAULT '',
          last_name TEXT NOT NULL DEFAULT '',
          company TEXT NOT NULL DEFAULT '',
          company_norm TEXT NOT NULL DEFAULT '',
          position TEXT NOT NULL DEFAULT '',
          connected_on TEXT NOT NULL DEFAULT '',
          import_id INTEGER REFERENCES linkedin_connection_imports(id) ON DELETE SET NULL,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          UNIQUE(user_id, profile_url)
        );
        INSERT INTO linkedin_connections__scoped (
          id,
          user_id,
          profile_url,
          first_name,
          last_name,
          company,
          company_norm,
          position,
          connected_on,
          import_id,
          created_at,
          updated_at
        )
        SELECT
          id,
          user_id,
          profile_url,
          first_name,
          last_name,
          company,
          company_norm,
          position,
          connected_on,
          import_id,
          created_at,
          updated_at
        FROM linkedin_connections;
        DROP TABLE linkedin_connections;
        ALTER TABLE linkedin_connections__scoped RENAME TO linkedin_connections;
        CREATE INDEX IF NOT EXISTS idx_linkedin_connections_company_norm
        ON linkedin_connections(company_norm);
        UPDATE linkedin_connections SET user_id = '' WHERE user_id IS NULL;
        UPDATE linkedin_connection_imports SET user_id = '' WHERE user_id IS NULL;
        """
    )


def _migrate_resume_assets_user_scope(conn: sqlite3.Connection) -> None:
    _ensure_column(conn, "resume_assets", "user_id", "TEXT")
    row = conn.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table' AND name = 'resume_assets'
          AND sql LIKE '%UNIQUE(user_id, sha256)%'
        """
    ).fetchone()
    if row is not None:
        conn.execute(
            "UPDATE resume_assets SET user_id = '' WHERE user_id IS NULL"
        )
        return
    conn.executescript(
        """
        CREATE TABLE resume_assets__scoped (
          id INTEGER PRIMARY KEY,
          user_id TEXT,
          original_filename TEXT NOT NULL,
          content_type TEXT NOT NULL,
          storage_path TEXT NOT NULL,
          sha256 TEXT NOT NULL,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          UNIQUE(user_id, sha256)
        );
        INSERT INTO resume_assets__scoped (
          id,
          user_id,
          original_filename,
          content_type,
          storage_path,
          sha256,
          created_at
        )
        SELECT
          id,
          user_id,
          original_filename,
          content_type,
          storage_path,
          sha256,
          created_at
        FROM resume_assets;
        DROP TABLE resume_assets;
        ALTER TABLE resume_assets__scoped RENAME TO resume_assets;
        UPDATE resume_assets SET user_id = '' WHERE user_id IS NULL;
        """
    )


def table_columns(conn: sqlite3.Connection | "Database", table: str) -> set[str]:
    from ml_job_swarm.db.postgres_backend import PostgresDatabase

    if isinstance(conn, PostgresDatabase):
        from ml_job_swarm.db.postgres_schema import postgres_table_columns

        return postgres_table_columns(conn, table)

    conn = _require_sqlite_connection(conn)
    if not table.replace("_", "").isalnum():
        raise ValueError(f"Invalid table name: {table}")

    rows = conn.execute(f'PRAGMA table_info("{table}")').fetchall()
    return {row["name"] for row in rows}


def _ensure_column(
    conn: sqlite3.Connection, table: str, column: str, definition: str
) -> None:
    if column in table_columns(conn, table):
        return
    conn.execute(f'ALTER TABLE "{table}" ADD COLUMN "{column}" {definition}')
