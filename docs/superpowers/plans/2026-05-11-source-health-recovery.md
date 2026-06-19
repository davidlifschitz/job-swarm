# Source health recovery implementation plan

## Scope

Update current source health display only. Do not delete friction events, change
refresh behavior, change source policy, or change adapter contracts.

## Files

- `ml_job_swarm/app.py`
- `tests/test_routes_admin_sources.py`
- `docs/superpowers/e2e-product-readiness.md`
- `docs/superpowers/plans/README.md`

## TDD Steps

- [x] Add failing admin route test for recovered source health.
- [x] Add focused helper logic in `_source_health_rows` to suppress stale
  friction from the current source-health table.
- [x] Keep friction log assertions proving the historical event remains visible.
- [x] Update readiness/plan index docs.
- [x] Run focused admin route tests and full suite.

## Acceptance Checks

- `uv run pytest tests/test_routes_admin_sources.py -q`
- `uv run pytest -q`
