# Live E2E smoke operator logs implementation plan

## Scope

Harden the existing local live E2E smoke command so failures are easier to
diagnose without changing the website workflow or adding CI execution.

## Files

- `scripts/live_e2e_smoke.py`
- `tests/test_live_e2e_smoke_script.py`
- `docs/superpowers/e2e-product-readiness.md`
- `docs/superpowers/plans/README.md`

## TDD Steps

- [x] Add a failing unit test showing `_start_server` should accept an artifact
  log path, send Uvicorn output there, and close the handle during cleanup.
- [x] Add a server handle that owns both the process and the log file.
- [x] Include `server_log_path` in the success summary and print the artifact
  directory to stderr before the run begins.
- [x] Add stderr progress markers and use `domcontentloaded` for the first
  local navigation so the smoke does not wait on unrelated network idle state.
- [x] Run focused smoke-script tests.
- [x] Run the full suite.
- [x] Run the live smoke command once and record evidence.

## Evidence

- `uv run pytest tests/test_live_e2e_smoke_script.py -q` -> 4 passed.
- `uv run pytest -q` -> 393 passed.
- `uv run --with uvicorn --with playwright python scripts/live_e2e_smoke.py`
  -> `browser_e2e_ok`, `jobs_seen=422`, `sources_attempted=1`,
  `sources_succeeded=1`, and `server_log_path` in the JSON summary.

## Acceptance Checks

- `uv run pytest tests/test_live_e2e_smoke_script.py -q`
- `uv run pytest -q`
- `uv run --with uvicorn --with playwright python scripts/live_e2e_smoke.py`
