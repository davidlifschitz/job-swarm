# Admin Run Detail Plan

## Tests First

- Add a route test that run history links to `/admin/runs/{id}`.
- Add a detail route test that inserts one run, one snapshot, and one friction
  event with sensitive details, then verifies safe rendering.
- Add a missing-run 404 route test.

## Implementation

- Add `GET /admin/runs/{run_id}`.
- Add `_ingestion_run_detail`, `_run_snapshot_rows`, and
  `_run_friction_rows` helpers.
- Add `admin_run_detail.html`.
- Link the run ID in `admin_runs.html`.

## Verification

- Run `uv run pytest tests/test_routes_admin_sources.py -q`.
- Run full `uv run pytest -q`.
- Browser-smoke the detail page against a temp seeded refresh DB.
