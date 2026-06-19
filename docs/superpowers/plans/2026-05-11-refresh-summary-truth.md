# Refresh summary truth implementation plan

## Scope

Make refresh summary counters honest without changing adapter behavior, source
policy, matching, or application workflows. Also close the observed no-LLM E2E
gap where public-refresh jobs could be saved from detail but vanished from Saved
Jobs because no fit-review row existed.

## Files

- `ml_job_swarm/ingest.py`
- `ml_job_swarm/app.py`
- `ml_job_swarm/cli.py`
- `ml_job_swarm/web/templates/dashboard.html`
- `ml_job_swarm/web/templates/admin_runs.html`
- `tests/test_ingest.py`
- `tests/test_routes_dashboard.py`
- `tests/test_routes_admin_sources.py`
- `tests/test_cli.py`
- `tests/test_job_decisions.py`
- `tests/test_routes_app_shell.py`
- `docs/superpowers/e2e-product-readiness.md`
- `docs/superpowers/plans/README.md`
- `README.md`

## TDD Steps

- [x] Add/adjust failing tests for attempted vs succeeded source counts.
- [x] Add failing no-credentials saved-job E2E test.
- [x] Update `RefreshSummary` and refresh aggregation.
- [x] Update web redirects, summary parsing, and templates.
- [x] Update CLI JSON output.
- [x] Let saved job export include no-fit-review saved jobs.
- [x] Add dashboard Save/Hide actions for rules-preview and unreviewed rows.
- [x] Preserve profile context in global dashboard nav.
- [x] Fix duplicate resume upload asset reuse.
- [x] Contain dashboard preview tables so action buttons are clickable.
- [x] Add central E2E readiness tracker and README pointer.
- [x] Run focused tests and inspect the UI summary text.

## Acceptance Checks

- `uv run pytest tests/test_ingest.py tests/test_routes_dashboard.py tests/test_routes_admin_sources.py tests/test_cli.py -q`
- `uv run pytest tests/test_job_decisions.py tests/test_routes_app_shell.py -q`
- `uv run pytest -q`
- Browser smoke against one live Anthropic Greenhouse seed: upload DOCX, create
  target profile, refresh public source, save no-LLM job, view Saved Jobs,
  prepare packet.
- Browser or HTML inspection confirms refresh summaries say attempted/succeeded,
  not misleading refreshed-only copy.
