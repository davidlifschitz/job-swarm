# Close Stale Public Jobs Implementation Plan

Spec: `docs/superpowers/specs/2026-05-10-close-stale-public-jobs-design.md`

## Goal

Keep the local job catalog current by closing stale postings only after successful public source refreshes.

## Ownership

- Controller-owned files:
  - `ml_job_swarm/ingest.py`
  - `ml_job_swarm/store.py`
  - `ml_job_swarm/filtering.py`
  - `ml_job_swarm/app.py`
  - `ml_job_swarm/cli.py`
  - `ml_job_swarm/web/templates/dashboard.html`
  - `ml_job_swarm/web/templates/admin_runs.html`
  - focused tests for ingestion, store schema, fit review visibility, dashboard/admin routes, and CLI output
  - this spec and plan pair

## TDD Steps

1. Add ingestion tests for closing missing jobs, reopening reappearing jobs, and preserving jobs on failed or suspicious-empty refreshes.
2. Add schema and summary tests for `jobs_closed`.
3. Add grouped-result visibility test proving closed jobs disappear from dashboard match groups.
4. Add dashboard/admin/CLI tests for `jobs_closed` counters.
5. Implement schema migration and refresh-result fields.
6. Track seen job IDs during successful processing and close stale open jobs for that source.
7. Surface `jobs_closed` in route redirects, templates, and CLI JSON.
8. Run focused tests, full suite, and a browser smoke against admin run history.

## Verification

```bash
uv run pytest tests/test_ingest.py tests/test_fit_review.py tests/test_store_schema.py tests/test_routes_dashboard.py tests/test_routes_admin_sources.py tests/test_cli.py -q
uv run pytest -q
```
