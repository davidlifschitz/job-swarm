-- Tier 2 Phase B: initial Postgres schema (parity with SQLite store.py)

CREATE TABLE IF NOT EXISTS companies (
  id BIGSERIAL PRIMARY KEY,
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
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS job_sources (
  id BIGSERIAL PRIMARY KEY,
  company_id BIGINT REFERENCES companies(id) ON DELETE CASCADE,
  url TEXT NOT NULL,
  source_type TEXT NOT NULL DEFAULT 'careers',
  policy_mode TEXT NOT NULL DEFAULT 'allowed',
  review_status TEXT NOT NULL DEFAULT 'pending',
  last_checked_at TIMESTAMPTZ,
  disabled_at TIMESTAMPTZ,
  notes TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(company_id, url)
);

CREATE TABLE IF NOT EXISTS company_source_review_queue (
  id BIGSERIAL PRIMARY KEY,
  company_name TEXT NOT NULL,
  requested_url TEXT,
  reason TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending',
  reviewed_at TIMESTAMPTZ,
  reviewed_by TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ingestion_runs (
  id BIGSERIAL PRIMARY KEY,
  started_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  finished_at TIMESTAMPTZ,
  status TEXT NOT NULL DEFAULT 'running',
  source_count INTEGER NOT NULL DEFAULT 0,
  jobs_seen INTEGER NOT NULL DEFAULT 0,
  jobs_added INTEGER NOT NULL DEFAULT 0,
  jobs_updated INTEGER NOT NULL DEFAULT 0,
  jobs_closed INTEGER NOT NULL DEFAULT 0,
  error TEXT
);

CREATE TABLE IF NOT EXISTS source_friction_events (
  id BIGSERIAL PRIMARY KEY,
  job_source_id BIGINT REFERENCES job_sources(id) ON DELETE SET NULL,
  ingestion_run_id BIGINT REFERENCES ingestion_runs(id) ON DELETE SET NULL,
  event_type TEXT NOT NULL,
  url TEXT NOT NULL,
  status_code INTEGER,
  details_json TEXT NOT NULL DEFAULT '{}',
  review_status TEXT NOT NULL DEFAULT 'unreviewed',
  reviewed_at TIMESTAMPTZ,
  reviewed_by TEXT,
  review_note TEXT NOT NULL DEFAULT '',
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS admin_audit_events (
  id BIGSERIAL PRIMARY KEY,
  actor TEXT NOT NULL DEFAULT 'local-admin',
  action TEXT NOT NULL,
  target_type TEXT NOT NULL,
  target_id TEXT NOT NULL,
  before_json TEXT NOT NULL DEFAULT '{}',
  after_json TEXT NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
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
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  started_at TIMESTAMPTZ,
  completed_at TIMESTAMPTZ,
  last_heartbeat_at TIMESTAMPTZ,
  cancel_requested_at TIMESTAMPTZ,
  UNIQUE(user_id, idempotency_key)
);

CREATE TABLE IF NOT EXISTS cloud_run_events (
  id BIGSERIAL PRIMARY KEY,
  run_id TEXT NOT NULL REFERENCES cloud_runs(id) ON DELETE CASCADE,
  event_type TEXT NOT NULL,
  status TEXT NOT NULL,
  stage TEXT NOT NULL,
  message TEXT NOT NULL,
  payload_json TEXT NOT NULL DEFAULT '{}',
  trace_id TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS job_snapshots (
  id BIGSERIAL PRIMARY KEY,
  ingestion_run_id BIGINT REFERENCES ingestion_runs(id) ON DELETE CASCADE,
  job_source_id BIGINT REFERENCES job_sources(id) ON DELETE SET NULL,
  external_id TEXT,
  title TEXT NOT NULL,
  company_name TEXT NOT NULL,
  location_text TEXT,
  remote_mode TEXT,
  raw_json TEXT NOT NULL DEFAULT '{}',
  content_hash TEXT NOT NULL,
  captured_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS jobs (
  id BIGSERIAL PRIMARY KEY,
  company_id BIGINT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
  job_source_id BIGINT REFERENCES job_sources(id) ON DELETE SET NULL,
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
  first_seen_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_seen_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  status TEXT NOT NULL DEFAULT 'open',
  UNIQUE(company_id, external_id)
);

CREATE TABLE IF NOT EXISTS resume_assets (
  id BIGSERIAL PRIMARY KEY,
  user_id TEXT,
  original_filename TEXT NOT NULL,
  content_type TEXT NOT NULL,
  storage_path TEXT NOT NULL,
  sha256 TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(user_id, sha256)
);

CREATE TABLE IF NOT EXISTS resume_parse_runs (
  id BIGSERIAL PRIMARY KEY,
  resume_asset_id BIGINT NOT NULL REFERENCES resume_assets(id) ON DELETE CASCADE,
  parser TEXT NOT NULL,
  parser_version TEXT NOT NULL,
  status TEXT NOT NULL,
  confidence DOUBLE PRECISION NOT NULL,
  vision_fallback_status TEXT NOT NULL DEFAULT 'not_needed',
  vision_fallback_consented_at TIMESTAMPTZ,
  error TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS resume_sections (
  id BIGSERIAL PRIMARY KEY,
  parse_run_id BIGINT NOT NULL REFERENCES resume_parse_runs(id) ON DELETE CASCADE,
  section_type TEXT NOT NULL,
  heading TEXT,
  text TEXT NOT NULL,
  sort_order INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS resume_keywords (
  id BIGSERIAL PRIMARY KEY,
  parse_run_id BIGINT NOT NULL REFERENCES resume_parse_runs(id) ON DELETE CASCADE,
  keyword TEXT NOT NULL,
  source_section TEXT,
  weight DOUBLE PRECISION NOT NULL DEFAULT 1.0
);

CREATE TABLE IF NOT EXISTS target_profiles (
  id BIGSERIAL PRIMARY KEY,
  user_id TEXT,
  resume_asset_id BIGINT REFERENCES resume_assets(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  version INTEGER NOT NULL DEFAULT 1,
  desired_titles_json TEXT NOT NULL DEFAULT '[]',
  levels_json TEXT NOT NULL DEFAULT '[]',
  locations_json TEXT NOT NULL DEFAULT '[]',
  remote_modes_json TEXT NOT NULL DEFAULT '[]',
  company_stages_json TEXT NOT NULL DEFAULT '[]',
  active INTEGER NOT NULL DEFAULT 1,
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS preference_answers (
  id BIGSERIAL PRIMARY KEY,
  target_profile_id BIGINT NOT NULL REFERENCES target_profiles(id) ON DELETE CASCADE,
  question_key TEXT NOT NULL,
  answer_json TEXT NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS llm_requests (
  id BIGSERIAL PRIMARY KEY,
  provider TEXT NOT NULL DEFAULT 'openrouter',
  model TEXT NOT NULL,
  feature TEXT NOT NULL,
  schema_version TEXT NOT NULL,
  status TEXT NOT NULL,
  request_hash TEXT NOT NULL,
  response_json TEXT NOT NULL DEFAULT '{}',
  error TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS resume_rewrite_suggestions (
  id BIGSERIAL PRIMARY KEY,
  resume_asset_id BIGINT NOT NULL REFERENCES resume_assets(id) ON DELETE CASCADE,
  job_id BIGINT REFERENCES jobs(id) ON DELETE CASCADE,
  target_profile_id BIGINT REFERENCES target_profiles(id) ON DELETE CASCADE,
  section_id BIGINT REFERENCES resume_sections(id) ON DELETE SET NULL,
  llm_request_id BIGINT REFERENCES llm_requests(id) ON DELETE SET NULL,
  suggestion_text TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'draft',
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS rules_filter_results (
  id BIGSERIAL PRIMARY KEY,
  job_id BIGINT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
  target_profile_id BIGINT NOT NULL REFERENCES target_profiles(id) ON DELETE CASCADE,
  outcome TEXT NOT NULL,
  score INTEGER NOT NULL,
  reasons_json TEXT NOT NULL DEFAULT '[]',
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS fit_reviews (
  id BIGSERIAL PRIMARY KEY,
  job_id BIGINT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
  target_profile_id BIGINT NOT NULL REFERENCES target_profiles(id) ON DELETE CASCADE,
  rules_filter_result_id BIGINT REFERENCES rules_filter_results(id) ON DELETE SET NULL,
  llm_request_id BIGINT REFERENCES llm_requests(id) ON DELETE SET NULL,
  fit_score INTEGER NOT NULL,
  label TEXT NOT NULL,
  reasons_json TEXT NOT NULL DEFAULT '[]',
  risks_json TEXT NOT NULL DEFAULT '[]',
  recommendation TEXT NOT NULL,
  profile_version INTEGER NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS job_decisions (
  id BIGSERIAL PRIMARY KEY,
  job_id BIGINT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
  target_profile_id BIGINT NOT NULL REFERENCES target_profiles(id) ON DELETE CASCADE,
  decision TEXT NOT NULL CHECK (decision IN ('saved', 'hidden')),
  notes TEXT NOT NULL DEFAULT '',
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(job_id, target_profile_id)
);

CREATE TABLE IF NOT EXISTS application_packets (
  id BIGSERIAL PRIMARY KEY,
  job_id BIGINT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
  target_profile_id BIGINT NOT NULL REFERENCES target_profiles(id) ON DELETE CASCADE,
  status TEXT NOT NULL DEFAULT 'prepared' CHECK (status IN ('prepared', 'submitted')),
  packet_json TEXT NOT NULL DEFAULT '{}',
  checklist_json TEXT NOT NULL DEFAULT '[]',
  manual_submit_url TEXT NOT NULL DEFAULT '',
  notes TEXT NOT NULL DEFAULT '',
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(job_id, target_profile_id)
);

CREATE TABLE IF NOT EXISTS contacts (
  id BIGSERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  email TEXT NOT NULL DEFAULT '',
  title TEXT NOT NULL DEFAULT '',
  notes TEXT NOT NULL DEFAULT '',
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS referral_contacts (
  id BIGSERIAL PRIMARY KEY,
  company_id BIGINT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
  contact_id BIGINT NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
  relationship TEXT NOT NULL DEFAULT '',
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(company_id, contact_id)
);

CREATE TABLE IF NOT EXISTS linkedin_connection_imports (
  id BIGSERIAL PRIMARY KEY,
  user_id TEXT,
  filename TEXT NOT NULL DEFAULT '',
  connection_count INTEGER NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS linkedin_connections (
  id BIGSERIAL PRIMARY KEY,
  user_id TEXT,
  profile_url TEXT NOT NULL,
  first_name TEXT NOT NULL DEFAULT '',
  last_name TEXT NOT NULL DEFAULT '',
  company TEXT NOT NULL DEFAULT '',
  company_norm TEXT NOT NULL DEFAULT '',
  position TEXT NOT NULL DEFAULT '',
  connected_on TEXT NOT NULL DEFAULT '',
  import_id BIGINT REFERENCES linkedin_connection_imports(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(user_id, profile_url)
);

CREATE INDEX IF NOT EXISTS idx_linkedin_connections_company_norm
ON linkedin_connections(company_norm);
