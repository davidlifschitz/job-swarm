# Live E2E smoke script implementation plan

## Scope

Add a local operator smoke command and docs. Do not add CI execution yet because
this uses live public network data and a browser runtime.

## Files

- `scripts/live_e2e_smoke.py`
- `tests/test_live_e2e_smoke_script.py`
- `README.md`
- `docs/superpowers/e2e-product-readiness.md`
- `docs/superpowers/plans/README.md`

## TDD Steps

- [x] Add focused tests for deterministic seed/resume generation and query
  summary parsing.
- [x] Add script with temp DB, generated seed/resume, local Uvicorn server, and
  Playwright browser workflow.
- [x] Document command and safety boundary.
- [x] Run focused tests and full suite.
- [x] Run the live smoke script once and record evidence.

## Evidence

- `uv run pytest tests/test_live_e2e_smoke_script.py -q` -> 3 passed.
- `uv run pytest -q` -> 392 passed.
- `uv run --with uvicorn --with playwright python scripts/live_e2e_smoke.py`
  -> `browser_e2e_ok`, `jobs_seen=422`, `sources_attempted=1`,
  `sources_succeeded=1`.

## Acceptance Checks

- `uv run pytest tests/test_live_e2e_smoke_script.py -q`
- `uv run pytest -q`
- `uv run --with uvicorn --with playwright python scripts/live_e2e_smoke.py`
