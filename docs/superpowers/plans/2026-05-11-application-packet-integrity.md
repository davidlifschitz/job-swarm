# Application packet integrity implementation plan

## Scope

Patch the application packet workflow without changing source refresh, fit
review, or live submission boundaries.

## Files

- `ml_job_swarm/app.py`
- `ml_job_swarm/web/templates/job_detail.html`
- `ml_job_swarm/web/templates/saved_jobs.html`
- `tests/test_routes_onboarding.py`
- `docs/superpowers/e2e-product-readiness.md`
- `docs/superpowers/plans/README.md`

## TDD Steps

- [x] Add failing tests for accepted resume rewrites missing from packet output.
- [x] Add failing test for re-preparing a submitted packet downgrading status.
- [x] Query accepted resume rewrites for the target profile and include only
  sanitized suggestion text in packet JSON.
- [x] Preserve `submitted` status during packet upsert.
- [x] Hide or relabel prepare controls for submitted packets.
- [x] Run focused tests.
- [x] Run full suite.

## Evidence

- `uv run pytest tests/test_routes_onboarding.py -q -k "application_packet"`
  -> 7 passed.
- `uv run pytest tests/test_routes_onboarding.py tests/test_routes_resume_workspace.py -q`
  -> 97 passed.
- `uv run pytest -q` -> 395 passed.
- `uv run --with uvicorn --with playwright python scripts/live_e2e_smoke.py`
  -> `browser_e2e_ok`, `jobs_seen=422`.

## Acceptance Checks

- `uv run pytest tests/test_routes_onboarding.py -q -k "application_packet"`
- `uv run pytest tests/test_routes_onboarding.py tests/test_routes_resume_workspace.py -q`
- `uv run pytest -q`
