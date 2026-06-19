# Admin Run History Implementation Plan

> Use `test-driven-development` for code changes, `goal-review` before accepting the slice, and `test-quality-review` before declaring it complete.

**Goal:** Implement the local ingestion run history page from `docs/superpowers/specs/2026-05-09-admin-run-history-design.md`.

## Scope Boundaries

V1 includes a read-only local run-history page.

V1 does not include Cloudflare scheduling, retry controls, external monitoring, or live scraping diagnostics.

## Files

- Modify: `ml_job_swarm/app.py`
- Modify: `ml_job_swarm/web/templates/admin_sources.html`
- Create: `ml_job_swarm/web/templates/admin_runs.html`
- Modify: `tests/test_routes_admin_sources.py`

## TDD Gates

- [x] Add route tests for empty and populated run history.
- [x] Add route test that `/admin/sources` links to `/admin/runs`.
- [x] Run focused tests and confirm missing behavior fails.
- [x] Implement smallest route/template/helper changes.
- [x] Run focused tests until green.
- [x] Run full suite.
- [x] Browser-smoke `/admin/runs`.
- [x] Run goal-review and test-quality-review before PR.

## Acceptance Checks

- Run history is visible without SQLite access.
- Counts and status are easy to scan.
- Page is read-only.
- Existing admin pages still pass their route tests.
