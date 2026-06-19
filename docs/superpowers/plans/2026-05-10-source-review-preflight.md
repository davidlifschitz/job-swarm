# Source Review Preflight Implementation Plan

Spec: `docs/superpowers/specs/2026-05-10-source-review-preflight-design.md`

## Goal

Add non-network policy/type/refreshability preflight to the admin source review queue.

## Ownership

- Controller-owned files:
  - `ml_job_swarm/catalog.py`
  - `ml_job_swarm/app.py`
  - `ml_job_swarm/web/templates/admin_sources.html`
  - `tests/test_routes_admin_sources.py`
  - this spec and plan pair

## TDD Steps

1. Add route tests for queue preflight.
   - Workable public source shows `workable` and `Ready`.
   - Unknown manual-link source shows `manual_link` and `Not refreshable`.
2. Expose source-type inference from catalog without changing approval behavior.
3. Enrich `_source_review_rows()` with policy/type/refreshability labels.
4. Render the new review queue columns.
5. Run focused admin-source route tests and full suite.

## Acceptance Checks

- Preflight is render-only and does not fetch external URLs.
- Approval still rejects non-allowed policies.
- Supported public source types line up with `app.state.adapter_registry.source_types()`.

## Verification

```bash
uv run pytest tests/test_routes_admin_sources.py -q
uv run pytest -q
```
