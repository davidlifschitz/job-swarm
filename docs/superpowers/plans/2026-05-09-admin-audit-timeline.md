# Admin Audit Timeline Implementation Plan

> Use `test-driven-development` for code changes, `goal-review` before accepting the slice, and `test-quality-review` before declaring it complete.

**Goal:** Implement the local admin audit timeline from `docs/superpowers/specs/2026-05-09-admin-audit-timeline-design.md`.

## Scope Boundaries

V1 includes a read-only, sanitized local audit page and a source-admin link.

V1 does not include hosted auth, audit mutation, external log shipping, or CSV export.

## Files

- Modify: `ml_job_swarm/app.py`
- Modify: `ml_job_swarm/web/templates/admin_sources.html`
- Create: `ml_job_swarm/web/templates/admin_audit.html`
- Modify: `tests/test_routes_admin_sources.py`

## TDD Gates

- [x] Add route tests for empty audit page, populated audit rows, and sanitization.
- [x] Add route test that `/admin/sources` links to `/admin/audit`.
- [x] Run focused tests and confirm missing behavior fails.
- [x] Implement the smallest route/template/helper changes.
- [x] Run focused tests until green.
- [x] Run full suite.
- [x] Browser-smoke `/admin/audit`.
- [x] Run goal-review and test-quality-review before PR.

## Acceptance Checks

- Audit events are visible without SQLite access.
- Sensitive keys are suppressed in before/after JSON.
- Page is read-only.
- Existing source-health and source-review behavior is unchanged.
