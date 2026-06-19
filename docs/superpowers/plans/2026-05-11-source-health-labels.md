# Source health labels implementation plan

## Scope

Presentation and row-shaping only for `/admin/sources`. Do not change refresh
actions, adapter contracts, source policy, or friction persistence.

## Files

- `ml_job_swarm/app.py`
- `ml_job_swarm/web/templates/admin_sources.html`
- `tests/test_routes_admin_sources.py`
- `docs/superpowers/e2e-product-readiness.md`
- `docs/superpowers/plans/README.md`

## TDD Steps

- [x] Add route tests for unchecked, healthy, needs-review, unsupported, and
  disabled source health labels.
- [x] Add `_source_health_status` helper and pass `health_status` fields to the
  template.
- [x] Render health badge separately from adapter refreshability badge.
- [x] Update readiness/plan index docs.
- [x] Run focused admin tests and full suite.

## Acceptance Checks

- `uv run pytest tests/test_routes_admin_sources.py -q`
- `uv run pytest -q`
