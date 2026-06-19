# Source Support Summary Implementation Plan

Spec: `docs/superpowers/specs/2026-05-10-source-support-summary-design.md`

## Goal

Render source support counts on `/admin/sources` so ingestion coverage is visible without row-by-row inspection.

## Ownership

- Controller-owned files:
  - `ml_job_swarm/app.py`
  - `ml_job_swarm/web/templates/admin_sources.html`
  - `tests/test_routes_admin_sources.py`
  - this spec and plan pair

## TDD Steps

1. Add a route test with one ready source, one unsupported source, and one disabled source.
2. Add a helper that summarizes source health row statuses.
3. Pass the summary to `admin_sources.html`.
4. Render a compact coverage panel.
5. Run focused admin route tests and full suite.

## Verification

```bash
uv run pytest tests/test_routes_admin_sources.py -q
uv run pytest -q
```
