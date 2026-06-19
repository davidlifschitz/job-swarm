# Dashboard LLM Readiness Implementation Plan

Spec: `docs/superpowers/specs/2026-05-10-dashboard-llm-readiness-design.md`

## Goal

Render provider readiness on the dashboard so public refresh and private LLM review are clearly separated.

## Ownership

- Controller-owned files:
  - `ml_job_swarm/app.py`
  - `ml_job_swarm/web/templates/dashboard.html`
  - `tests/test_routes_dashboard.py`
  - this spec and plan pair

## TDD Steps

1. Add dashboard route tests for unavailable and available fit-review states.
2. Pass `fit_review_available` into dashboard render contexts.
3. Render a readiness message and disable only LLM-dependent buttons when unavailable.
4. Run focused dashboard tests and full suite.
5. Browser smoke the dashboard.

## Verification

```bash
uv run pytest tests/test_routes_dashboard.py -q
uv run pytest -q
```
