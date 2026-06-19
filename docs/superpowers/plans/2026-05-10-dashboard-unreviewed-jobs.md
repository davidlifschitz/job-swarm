# Dashboard Unreviewed Jobs Implementation Plan

Spec: `docs/superpowers/specs/2026-05-10-dashboard-unreviewed-jobs-design.md`

## Goal

Render jobs waiting for fit review on the dashboard so public refresh has visible output before LLM scoring.

## Ownership

- Controller-owned files:
  - `ml_job_swarm/app.py`
  - `ml_job_swarm/web/templates/dashboard.html`
  - `tests/test_routes_dashboard.py`
  - this spec and plan pair

## TDD Steps

1. Add route tests:
   - unreviewed open job appears in `Jobs waiting for fit review`
   - current reviewed job does not appear in that section
   - preference update can leave old reviewed jobs waiting for the new profile version
2. Add `_unreviewed_job_rows()`.
3. Pass `unreviewed_jobs` into dashboard render contexts.
4. Render a compact waiting-list table.
5. Run focused and full tests, then browser-smoke the dashboard.

## Verification

```bash
uv run pytest tests/test_routes_dashboard.py -q
uv run pytest -q
```
