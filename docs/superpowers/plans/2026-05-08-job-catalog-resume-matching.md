# Job Catalog and Resume Matching Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `subagent-driven-development` or `executing-plans` to implement this plan task-by-task. Use `test-driven-development` for production behavior, `goal-review` before accepting scope changes, and `test-quality-review` before declaring any phase complete. Steps use checklist syntax for tracking.

**Goal:** Build the V1 local-first `ml-job-swarm` product from the approved design spec: daily curated company catalog, resume/profile extraction, rules-first filtering, OpenRouter fit review, grouped results UI, admin source health, and strict tests.

**Architecture:** Create a new root-level Python package and web app; leave `Legacy/` untouched. SQLite is the local source of truth. External network/model behavior is isolated behind adapters and mocked in tests by default.

**Tech Stack:** Python 3.12+, FastAPI, Jinja2, SQLite, pytest, httpx, python-docx, PyMuPDF, Pydantic, ruff/typing-friendly pure Python modules.

---

## Inputs

- Approved spec: `docs/superpowers/specs/2026-05-08-job-catalog-resume-matching-design.md`
- Visuals: `design-specs/`
- Review skills:
  - `.agents/skills/goal-review/SKILL.md`
  - `.agents/skills/test-quality-review/SKILL.md`

## Hard Scope Boundaries

V1 includes local-first catalog, resume parsing, fit review, grouped UI, and admin source health.

V1 does not include:

- No LinkedIn or Indeed ingestion
- auth-gated, cookie-based, CAPTCHA bypass, or hidden-session scraping
- final application submission
- outreach/referrals/CRM/reminders
- Cloudflare scheduling as a product dependency
- Hermes/browser-use parallel workflow QA as a completion blocker
- full resume designer

## File Structure

Create:

```text
pyproject.toml
README.md
ml_job_swarm/
  __init__.py
  app.py
  catalog.py
  filtering.py
  ingest.py
  llm.py
  models.py
  profile.py
  resume_extract.py
  source_policy.py
  store.py
  web/
    templates/
      base.html
      dashboard.html
      onboarding.html
      admin_sources.html
    static/
      app.css
data/
  seed_companies.json
tests/
  fixtures/
  test_*.py
```

Ownership boundaries:

- `store.py` owns schema, migrations, and SQLite query helpers.
- `models.py` owns Pydantic/domain models only.
- `source_policy.py` owns allow/block decisions only.
- `catalog.py` owns company seed and user source queue.
- `ingest.py` owns daily refresh orchestration and source adapters.
- `resume_extract.py` owns local parse and vision fallback trigger metadata.
- `llm.py` owns OpenRouter request contracts and schema validation.
- `profile.py` owns preferences and target profile versioning.
- `filtering.py` owns rules filter and fit-review orchestration.
- `app.py` and `web/` own HTTP/UI only.

## Subagent Ownership Plan

Use parallel workers only after this plan is accepted.

- Worker A: schema/store/models. Owns `store.py`, `models.py`, storage tests.
- Worker B: catalog/source policy/ingest. Owns `catalog.py`, `source_policy.py`, `ingest.py`, seed data, ingestion tests.
- Worker C: resume/profile/LLM contracts. Owns `resume_extract.py`, `profile.py`, `llm.py`, resume and contract tests.
- Worker D: filtering/scoring. Owns `filtering.py`, fit-review tests, fixtures.
- Worker E: web UI/admin. Owns `app.py`, `web/`, route and UI smoke tests.
- Controller: integrates shared models/schema, runs full tests, resolves cross-worker drift.

Do not let multiple workers edit `store.py` or `models.py` simultaneously. Schema changes are controller-owned after Task 2.

## Review Gates

- Run `goal-review` after writing this plan and after any plan-scope change.
- Run `test-quality-review` before implementation completion and before any PR is marked ready.
- Every phase has a TDD gate: write focused failing tests first, verify failure, implement minimal code, verify pass.
- Full-suite pass is required before calling the implementation complete.

## Execution Discipline

- Track checklist status task-by-task; do not batch-mark tasks complete at the end.
- Keep `store.py` and `models.py` controller-owned after Task 2 lands.
- Do not run multiple schema/model editors in parallel.
- The first implementation PR should cover only Task 1 and Task 2 so the package skeleton and SQLite schema stabilize before parallel feature workers start.
- After the first implementation PR, run `goal-review` and `test-quality-review` before opening broader parallel work.

## Implementation Status

Status reconciled after the implementation stack landed on `main`.

- PRs #34-#44 implemented the V1 foundation through full verification.
- PRs #39-#44 were merged into `main` on 2026-05-08 after the fit-review, onboarding, resume workspace, admin source health, and end-to-end catalog matching slices were rebased and rechecked.
- Final verification on synced `main`: `uv run pytest -q` passed with 103 tests, and `uv run ml-job-swarm --help` verified the cron-friendly refresh command is packaged.
- This checklist now reflects completed implementation state; future work should open a new plan or append a follow-up section instead of restarting these tasks.

## Seed Catalog Quality Gate

The initial company catalog is product-critical data, not filler.

Before ingestion work is considered complete:

- the seed list must contain roughly 50 manually reviewed companies
- every company must have a public careers URL or reviewed ATS URL
- company tags must cover AI labs, AI infrastructure, big tech, quant, fintech, and developer tools
- source URLs must pass `source_policy` or be explicitly queued for review
- stale, guessed, or generated-only career URLs are not acceptable as final seed entries

## UI Stack Decision Note

FastAPI with Jinja templates is the default V1 UI stack because it is simple, local-first, testable with route tests, and sufficient for the grouped dashboard/admin pages. Revisit the UI stack only if implementation reveals a concrete blocker.

---

## Task 1: Project Skeleton

**Files:**
- Create: `pyproject.toml`
- Create: `README.md`
- Create: `ml_job_swarm/__init__.py`
- Create: `tests/test_project_skeleton.py`

**Subagent suitability:** yes, isolated. Assign to Worker A or controller.

**Integration risk:** low. Keep dependencies minimal and avoid touching `Legacy/`.

- [x] **Step 1: Write failing skeleton tests**

  Create `tests/test_project_skeleton.py` with assertions:

  ```python
  import importlib.metadata

  import ml_job_swarm


  def test_package_imports():
      assert ml_job_swarm.__all__ == ["__version__"]


  def test_project_metadata_exists():
      assert importlib.metadata.metadata("ml-job-swarm")["Name"] == "ml-job-swarm"
  ```

- [x] **Step 2: Verify tests fail**

  Run:

  ```bash
  uv run pytest tests/test_project_skeleton.py -q
  ```

  Expected: import/package metadata failure.

- [x] **Step 3: Implement minimal skeleton**

  Create package metadata and `ml_job_swarm/__init__.py` with `__version__`.

- [x] **Step 4: Verify pass**

  Run:

  ```bash
  uv run pytest tests/test_project_skeleton.py -q
  ```

- [x] **Step 5: Acceptance check**

  `uv run python -c "import ml_job_swarm; print(ml_job_swarm.__version__)"` prints a version.

## Task 2: SQLite Schema and Store

**Files:**
- Create: `ml_job_swarm/store.py`
- Create: `ml_job_swarm/models.py`
- Create: `tests/test_store_schema.py`

**Subagent suitability:** yes, but schema ownership becomes controller-owned after this task.

**Integration risk:** high. All future workers depend on stable table names and model fields.

- [x] **Step 1: Write failing schema tests**

  Tests must create an in-memory DB and assert these tables exist:

  ```text
  companies
  job_sources
  company_source_review_queue
  ingestion_runs
  source_friction_events
  admin_audit_events
  job_snapshots
  jobs
  resume_assets
  resume_parse_runs
  resume_sections
  resume_keywords
  target_profiles
  preference_answers
  resume_rewrite_suggestions
  rules_filter_results
  fit_reviews
  llm_requests
  ```

  Also assert `target_profiles.version`, `fit_reviews.fit_score`, `fit_reviews.label`, and `resume_parse_runs.vision_fallback_consented_at` exist.

- [x] **Step 2: Verify schema tests fail**

  Run:

  ```bash
  uv run pytest tests/test_store_schema.py -q
  ```

- [x] **Step 3: Implement schema init**

  `store.py` should expose:

  ```python
  def connect(path: str | Path = ":memory:") -> sqlite3.Connection: ...
  def init_db(conn: sqlite3.Connection) -> None: ...
  def table_columns(conn: sqlite3.Connection, table: str) -> set[str]: ...
  ```

- [x] **Step 4: Add domain models**

  `models.py` should define enums/literals for:

  ```text
  PolicyMode: allowed, blocked, manual_link
  FitLabel: Strong fit, Possible fit, Mismatch risk, Filtered out
  RulesOutcome: pass, soft_pass, reject
  FrictionEventType: policy_blocked, captcha_or_login, rate_limited, blocked_response, layout_changed, empty_suspicious, manual_review_needed, timeout
  ```

- [x] **Step 5: Verify pass**

  Run:

  ```bash
  uv run pytest tests/test_store_schema.py -q
  ```

- [x] **Step 6: Acceptance check**

  Schema can be initialized twice without error and all foreign keys are enabled.

## Task 3: Source Policy

**Files:**
- Create: `ml_job_swarm/source_policy.py`
- Create: `tests/test_source_policy.py`

**Subagent suitability:** yes, isolated. Assign to Worker B.

**Integration risk:** medium. Policy results feed catalog and ingestion.

- [x] **Step 1: Write failing source-policy tests**

  Cover:

  ```python
  def test_allows_public_ats_urls(): ...
  def test_blocks_linkedin_and_indeed(): ...
  def test_blocks_auth_or_login_urls(): ...
  def test_blocks_search_result_proxy_urls(): ...
  def test_manual_link_for_unknown_non_company_source(): ...
  ```

- [x] **Step 2: Verify tests fail**

  Run:

  ```bash
  uv run pytest tests/test_source_policy.py -q
  ```

- [x] **Step 3: Implement policy classifier**

  Expose:

  ```python
  @dataclass(frozen=True)
  class SourcePolicyResult:
      mode: Literal["allowed", "blocked", "manual_link"]
      reason: str
      normalized_url: str | None

  def classify_source_url(url: str) -> SourcePolicyResult: ...
  ```

- [x] **Step 4: Verify pass**

  Run:

  ```bash
  uv run pytest tests/test_source_policy.py -q
  ```

- [x] **Step 5: Acceptance check**

  LinkedIn/Indeed/auth/CAPTCHA-like/login URLs never return `allowed`.

## Task 4: Company Catalog and Review Queue

**Files:**
- Create: `data/seed_companies.json`
- Create: `ml_job_swarm/catalog.py`
- Create: `tests/test_catalog.py`

**Subagent suitability:** yes, isolated after Task 2 and Task 3. Assign to Worker B.

**Integration risk:** medium. Seed data quality affects ingestion and UI.

- [x] **Step 1: Write failing catalog tests**

  Tests:

  ```python
  def test_seed_catalog_loads_at_least_50_companies(): ...
  def test_seed_company_has_required_fields(): ...
  def test_user_added_source_enters_review_queue(): ...
  def test_blocked_user_source_records_policy_result(): ...
  ```

- [x] **Step 2: Verify tests fail**

  Run:

  ```bash
  uv run pytest tests/test_catalog.py -q
  ```

- [x] **Step 3: Add seed catalog**

  Include roughly 50 high-quality companies across AI labs, AI infra, big tech, quant, fintech, and developer tools. Each entry must include:

  ```json
  {
    "name": "Example",
    "aliases": [],
    "tags": ["ai_infra"],
    "stage": "growth",
    "priority_tier": 1,
    "careers_url": "https://example.com/careers",
    "ats_type": "unknown"
  }
  ```

- [x] **Step 4: Implement catalog functions**

  Expose:

  ```python
  def load_seed_companies(path: Path) -> list[SeedCompany]: ...
  def import_seed_companies(conn: sqlite3.Connection, path: Path) -> int: ...
  def submit_company_source(conn: sqlite3.Connection, company_name: str, source_url: str) -> int: ...
  ```

- [x] **Step 5: Verify pass**

  Run:

  ```bash
  uv run pytest tests/test_catalog.py -q
  ```

- [x] **Step 6: Acceptance check**

  User-added source is queued; it does not immediately perform live scraping.

## Task 5: Daily Ingestion Orchestration

**Files:**
- Create: `ml_job_swarm/ingest.py`
- Create: `tests/fixtures/greenhouse_jobs.json`
- Create: `tests/fixtures/lever_jobs.json`
- Create: `tests/test_ingest.py`

**Subagent suitability:** yes, but keep adapter scope narrow. Assign to Worker B.

**Integration risk:** high. Must not introduce live external side effects into tests.

- [x] **Step 1: Write failing ingestion tests**

  Tests:

  ```python
  def test_refresh_records_ingestion_run(): ...
  def test_refresh_inserts_snapshots_and_canonical_jobs(): ...
  def test_refresh_dedupes_by_external_id_or_hash(): ...
  def test_failed_refresh_preserves_existing_jobs(): ...
  def test_policy_block_records_friction_event(): ...
  def test_empty_suspicious_does_not_close_all_jobs_immediately(): ...
  ```

- [x] **Step 2: Verify tests fail**

  Run:

  ```bash
  uv run pytest tests/test_ingest.py -q
  ```

- [x] **Step 3: Implement adapter interface**

  Expose:

  ```python
  class JobSourceAdapter(Protocol):
      def fetch_jobs(self, source: JobSource) -> list[RawJob]: ...

  def refresh_source(conn: sqlite3.Connection, source_id: int, adapter: JobSourceAdapter) -> RefreshResult: ...
  def refresh_due_sources(conn: sqlite3.Connection, adapter_registry: AdapterRegistry) -> RefreshSummary: ...
  ```

  Test adapters must be in-memory/fake only.

- [x] **Step 4: Implement snapshot/canonical update**

  Insert append-only snapshots, then update canonical `jobs` rows.

- [x] **Step 5: Implement friction logging**

  Policy blocks, timeouts, rate limits, auth/login/CAPTCHA, and suspicious empty results create `source_friction_events`.

- [x] **Step 6: Verify pass**

  Run:

  ```bash
  uv run pytest tests/test_ingest.py -q
  ```

- [x] **Step 7: Acceptance check**

  A daily refresh command can run with fake adapters and produce deterministic DB rows.

## Task 6: Resume Extraction and Vision Fallback Contract

**Files:**
- Create: `ml_job_swarm/resume_extract.py`
- Create: `tests/fixtures/resume_simple.txt`
- Create: `tests/fixtures/resume_low_confidence.txt`
- Create: `tests/test_resume_extract.py`

**Subagent suitability:** yes. Assign to Worker C.

**Integration risk:** high for privacy. Never log raw resume text in tests or app logs.

- [x] **Step 1: Write failing resume extraction tests**

  Tests:

  ```python
  def test_extracts_sections_from_plain_text_fixture(): ...
  def test_low_confidence_resume_sets_fallback_flag(): ...
  def test_vision_fallback_requires_consent_timestamp(): ...
  def test_resume_prompt_injection_is_treated_as_content(): ...
  def test_raw_resume_text_not_in_parse_run_metadata(): ...
  ```

- [x] **Step 2: Verify tests fail**

  Run:

  ```bash
  uv run pytest tests/test_resume_extract.py -q
  ```

- [x] **Step 3: Implement parser contract**

  Expose:

  ```python
  @dataclass(frozen=True)
  class ResumeParseResult:
      sections: dict[str, str]
      keywords: list[str]
      parser_name: str
      parser_confidence: float
      warnings: list[str]
      needs_vision_fallback: bool

  def parse_resume_text(text: str) -> ResumeParseResult: ...
  def record_parse_run(conn: sqlite3.Connection, resume_asset_id: int, result: ResumeParseResult, consented_at: datetime | None) -> int: ...
  ```

- [x] **Step 4: Add PDF/DOCX adapters behind interface**

  Plan for `python-docx` and PyMuPDF. Tests may use text fixtures first; binary fixtures can be added after skeleton parsing works.

- [x] **Step 5: Verify pass**

  Run:

  ```bash
  uv run pytest tests/test_resume_extract.py -q
  ```

- [x] **Step 6: Acceptance check**

  Low-confidence parse requires explicit consent before a vision fallback request can be created.

## Task 7: OpenRouter Contract Layer

**Files:**
- Create: `ml_job_swarm/llm.py`
- Create: `tests/test_llm_contracts.py`

**Subagent suitability:** yes. Assign to Worker C.

**Integration risk:** high. All tests must mock provider calls.

- [x] **Step 1: Write failing LLM contract tests**

  Tests:

  ```python
  def test_profile_draft_schema_validates(): ...
  def test_questionnaire_schema_validates_fixed_ids(): ...
  def test_resume_rewrite_schema_validates(): ...
  def test_fit_gate_requires_score_label_reasons_risks(): ...
  def test_schema_failure_retries_once_then_records_failure(): ...
  def test_llm_request_metadata_omits_raw_private_prompt(): ...
  ```

- [x] **Step 2: Verify tests fail**

  Run:

  ```bash
  uv run pytest tests/test_llm_contracts.py -q
  ```

- [x] **Step 3: Implement schemas**

  Pydantic models:

  ```text
  ProfileDraftResponse
  QuestionnaireResponse
  ResumeRewriteResponse
  FitGateResponse
  VisionFallbackResponse
  ```

- [x] **Step 4: Implement request metadata recording**

  `llm_requests` stores provider/model/schema/status/input reference only.

- [x] **Step 5: Verify pass**

  Run:

  ```bash
  uv run pytest tests/test_llm_contracts.py -q
  ```

- [x] **Step 6: Acceptance check**

  No test or log path stores raw resume content or raw private prompt text.

## Task 8: Preferences and Target Profiles

**Files:**
- Create: `ml_job_swarm/profile.py`
- Create: `tests/test_profile.py`

**Subagent suitability:** yes. Assign to Worker C.

**Integration risk:** medium. Profile versioning affects fit review invalidation.

- [x] **Step 1: Write failing profile tests**

  Tests:

  ```python
  def test_create_target_profile_version_one(): ...
  def test_preference_update_increments_profile_version(): ...
  def test_fixed_question_ids_are_required(): ...
  def test_old_fit_reviews_do_not_match_current_profile_version(): ...
  ```

- [x] **Step 2: Verify tests fail**

  Run:

  ```bash
  uv run pytest tests/test_profile.py -q
  ```

- [x] **Step 3: Implement profile functions**

  Expose:

  ```python
  REQUIRED_PREFERENCE_IDS = ["role", "level", "location", "work_mode", "company_stage"]
  def create_target_profile(conn, resume_asset_id, keywords, preferences) -> int: ...
  def update_preferences(conn, target_profile_id, preferences) -> int: ...
  def current_profile_version(conn, target_profile_id) -> int: ...
  ```

- [x] **Step 4: Verify pass**

  Run:

  ```bash
  uv run pytest tests/test_profile.py -q
  ```

- [x] **Step 5: Acceptance check**

  Dashboard queries can filter fit reviews by current profile version.

## Task 9: Rules Filter

**Files:**
- Create: `ml_job_swarm/filtering.py`
- Create: `tests/test_rules_filter.py`

**Subagent suitability:** yes. Assign to Worker D.

**Integration risk:** medium. Rules must be conservative and not over-filter.

- [x] **Step 1: Write failing rules tests**

  Tests:

  ```python
  def test_role_match_passes(): ...
  def test_adjacent_role_soft_passes(): ...
  def test_clear_unrelated_role_rejects(): ...
  def test_seniority_mismatch_soft_passes_for_llm_review_when_skills_match(): ...
  def test_explicit_location_mismatch_rejects(): ...
  def test_unknown_work_mode_soft_passes(): ...
  ```

- [x] **Step 2: Verify tests fail**

  Run:

  ```bash
  uv run pytest tests/test_rules_filter.py -q
  ```

- [x] **Step 3: Implement rules filter**

  Expose:

  ```python
  def apply_rules(job: Job, company: Company, target_profile: TargetProfile) -> RulesFilterResult: ...
  ```

  Outcomes: `pass`, `soft_pass`, `reject`.

- [x] **Step 4: Verify pass**

  Run:

  ```bash
  uv run pytest tests/test_rules_filter.py -q
  ```

- [x] **Step 5: Acceptance check**

  Seniority mismatch with skill overlap is not silently shown as strong; it proceeds to LLM fit review.

## Task 10: Fit Review Orchestration

**Files:**
- Modify: `ml_job_swarm/filtering.py`
- Modify: `ml_job_swarm/llm.py`
- Create: `tests/test_fit_review.py`

**Subagent suitability:** yes after Tasks 7-9. Assign to Worker D.

**Integration risk:** high. This bridges rules, profile versioning, LLM metadata, and dashboard semantics.

- [x] **Step 1: Write failing fit-review tests**

  Tests:

  ```python
  def test_strong_fit_is_visible(): ...
  def test_possible_fit_is_visible(): ...
  def test_mismatch_risk_is_hidden_by_default(): ...
  def test_filtered_out_is_stored_not_visible(): ...
  def test_fit_review_records_current_profile_version(): ...
  def test_fit_review_records_llm_request_id(): ...
  ```

- [x] **Step 2: Verify tests fail**

  Run:

  ```bash
  uv run pytest tests/test_fit_review.py -q
  ```

- [x] **Step 3: Implement orchestration**

  Expose:

  ```python
  def review_candidate_job(conn, job_id: int, target_profile_id: int, llm_client: FitGateClient) -> int: ...
  def visible_company_results(conn, target_profile_id: int) -> list[CompanyResult]: ...
  ```

- [x] **Step 4: Verify pass**

  Run:

  ```bash
  uv run pytest tests/test_fit_review.py -q
  ```

- [x] **Step 5: Acceptance check**

  Company results include visible matches and mismatch counts separately.

## Task 11: Web App and First-Run Wizard

**Files:**
- Create: `ml_job_swarm/app.py`
- Create: `ml_job_swarm/web/templates/base.html`
- Create: `ml_job_swarm/web/templates/onboarding.html`
- Create: `ml_job_swarm/web/templates/dashboard.html`
- Create: `ml_job_swarm/web/static/app.css`
- Create: `tests/test_routes_onboarding.py`

**Subagent suitability:** yes after Tasks 2, 6, 8, 10. Assign to Worker E.

**Integration risk:** high. UI must not invoke live model/network by default.

- [x] **Step 1: Write failing route tests**

  Tests with FastAPI `TestClient`:

  ```python
  def test_onboarding_page_loads(): ...
  def test_resume_upload_requires_supported_type(): ...
  def test_preferences_missing_disables_matching(): ...
  def test_dashboard_groups_jobs_by_company(): ...
  def test_mismatch_risks_are_collapsed_data_not_main_rows(): ...
  ```

- [x] **Step 2: Verify tests fail**

  Run:

  ```bash
  uv run pytest tests/test_routes_onboarding.py -q
  ```

- [x] **Step 3: Implement app factory**

  Expose:

  ```python
  def create_app(db_path: str | Path = ":memory:") -> FastAPI: ...
  ```

- [x] **Step 4: Implement first-run screens**

  Pages:

  - upload/resume review
  - preferences
  - dashboard

- [x] **Step 5: Verify pass**

  Run:

  ```bash
  uv run pytest tests/test_routes_onboarding.py -q
  ```

- [x] **Step 6: Acceptance check**

  App can render dashboard with fixture data and no live external calls.

## Task 12: Resume Workspace UI

**Files:**
- Modify: `ml_job_swarm/app.py`
- Modify: `ml_job_swarm/web/templates/dashboard.html`
- Modify: `ml_job_swarm/web/static/app.css`
- Create: `tests/test_routes_resume_workspace.py`

**Subagent suitability:** yes after Task 11. Assign to Worker E.

**Integration risk:** medium. Keep section rewrite scoped to one selected section.

- [x] **Step 1: Write failing route tests**

  Tests:

  ```python
  def test_resume_sections_render_as_clickable_items(): ...
  def test_rewrite_suggestion_requires_section_id(): ...
  def test_rewrite_suggestion_records_llm_metadata(): ...
  def test_accepting_suggestion_updates_generated_suggestion_not_raw_resume(): ...
  ```

- [x] **Step 2: Verify tests fail**

  Run:

  ```bash
  uv run pytest tests/test_routes_resume_workspace.py -q
  ```

- [x] **Step 3: Implement section UI and rewrite route**

  Add route for selected-section suggestions. Mock LLM in tests.

- [x] **Step 4: Verify pass**

  Run:

  ```bash
  uv run pytest tests/test_routes_resume_workspace.py -q
  ```

- [x] **Step 5: Acceptance check**

  Full resume designer controls do not exist in V1 UI.

## Task 13: Admin Source Health Page

**Files:**
- Create: `ml_job_swarm/web/templates/admin_sources.html`
- Modify: `ml_job_swarm/app.py`
- Create: `tests/test_routes_admin_sources.py`

**Subagent suitability:** yes after Task 5. Assign to Worker E.

**Integration risk:** medium. Admin actions must audit and sanitize.

- [x] **Step 1: Write failing admin tests**

  Tests:

  ```python
  def test_admin_sources_page_lists_source_health(): ...
  def test_latest_friction_event_is_visible(): ...
  def test_disable_source_records_admin_audit_event(): ...
  def test_export_friction_csv_has_no_secrets_or_raw_resume_text(): ...
  ```

- [x] **Step 2: Verify tests fail**

  Run:

  ```bash
  uv run pytest tests/test_routes_admin_sources.py -q
  ```

- [x] **Step 3: Implement admin page**

  Show source status, failure count, latest event, recommendation, and local-only actions.

- [x] **Step 4: Verify pass**

  Run:

  ```bash
  uv run pytest tests/test_routes_admin_sources.py -q
  ```

- [x] **Step 5: Acceptance check**

  No cookies, secrets, raw resumes, browser profiles, or raw prompt logs appear in admin output.

## Task 14: End-to-End Integration Fixtures

**Files:**
- Create: `tests/test_end_to_end_catalog_matching.py`
- Create: `tests/fixtures/job_descriptions/*.txt`
- Create: `tests/fixtures/resumes/*.txt`

**Subagent suitability:** yes, but controller should review. Assign to Worker D or controller.

**Integration risk:** high. This catches drift across modules.

- [x] **Step 1: Write failing E2E tests**

  Tests:

  ```python
  def test_daily_refresh_then_profile_matching_flow(): ...
  def test_seniority_mismatch_goes_to_mismatch_risks(): ...
  def test_profile_version_change_hides_old_fit_reviews(): ...
  def test_policy_blocked_source_appears_in_admin_not_results(): ...
  ```

- [x] **Step 2: Verify tests fail**

  Run:

  ```bash
  uv run pytest tests/test_end_to_end_catalog_matching.py -q
  ```

- [x] **Step 3: Implement missing integration glue**

  Add only glue needed to make existing module contracts work together.

- [x] **Step 4: Verify pass**

  Run:

  ```bash
  uv run pytest tests/test_end_to_end_catalog_matching.py -q
  ```

- [x] **Step 5: Acceptance check**

  One local fixture flow goes from seed catalog to grouped results without live network or model calls.

## Task 15: Full Verification and Review Gates

**Files:**
- Modify only docs/tests as required by review findings.

**Subagent suitability:** controller-owned. Do not delegate final integration blindly.

**Integration risk:** highest. This is where shared contract drift is caught.

- [x] **Step 1: Run full tests**

  Run:

  ```bash
  uv run pytest -q
  ```

- [x] **Step 2: Run route/UI smoke subset**

  Run:

  ```bash
  uv run pytest tests/test_routes_onboarding.py tests/test_routes_resume_workspace.py tests/test_routes_admin_sources.py -q
  ```

- [x] **Step 3: Apply `goal-review`**

  Review implemented behavior against:

  ```text
  docs/superpowers/specs/2026-05-08-job-catalog-resume-matching-design.md
  ```

  Blocking examples:

  - Cloudflare required for V1
  - LinkedIn/Indeed ingestion enabled
  - hidden-session scraping added
  - application workflow added
  - mismatch-risk jobs shown as normal matches

- [x] **Step 4: Apply `test-quality-review`**

  Blocking examples:

  - happy-path-only ingestion tests
  - OpenRouter schemas not tested
  - privacy/logging not tested
  - source-policy blocked cases missing
  - no profile-version invalidation test
  - no admin friction/audit tests

- [x] **Step 5: Fix review findings**

  Add tests first for any behavior gap, then patch implementation.

- [x] **Step 6: Final acceptance**

  All relevant tests pass, review gates pass, and no V2-only feature is required for V1.

## V2 Parking Lot

Do not implement during V1 unless the user explicitly re-scopes:

- Cloudflare scheduler/deployment
- larger generated company catalog
- authenticated/user-mediated source integrations
- full resume designer and exports
- application prep/submission workflow
- Hermes/browser-use parallel adversarial QA

## Execution Handoff

Plan complete when saved and reviewed. Execution options:

1. **Subagent-driven implementation, recommended:** dispatch fresh workers by ownership boundary, review after each phase, controller integrates shared schema and full test pass.
2. **Inline execution:** implement sequentially in this session using `executing-plans`, with checkpoints after each phase.

Before executing, run `goal-review` on this plan. After each implementation phase, run focused tests and update the checklist. Before final completion, run `test-quality-review`.
