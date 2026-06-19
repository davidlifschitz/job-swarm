# Source Submission UI Implementation Plan

> Use `test-driven-development` for code changes, `goal-review` before accepting the slice, and `test-quality-review` before declaring it complete.

**Goal:** Implement the local source-submission UI from `docs/superpowers/specs/2026-05-09-source-submission-ui-design.md`.

## Scope Boundaries

V1 includes a local form that submits into the existing review queue.

V1 does not include live scraping, policy bypass, auth-gated setup, CAPTCHA/cookie support, or hosted auth.

## Files

- Modify: `ml_job_swarm/app.py`
- Modify: `ml_job_swarm/web/templates/admin_sources.html`
- Create: `ml_job_swarm/web/templates/source_new.html`
- Modify: `tests/test_routes_admin_sources.py`

## TDD Gates

- [x] Add route tests for form render, allowed submission, blocked submission, and missing fields.
- [x] Add route test that `/admin/sources` links to `/sources/new`.
- [x] Run focused tests and confirm missing behavior fails.
- [x] Implement smallest route/template changes.
- [x] Run focused tests until green.
- [x] Run full suite.
- [x] Browser-smoke `/sources/new`.
- [x] Run goal-review and test-quality-review before PR.

## Acceptance Checks

- User-added sources are queued, not directly approved.
- Blocked source submissions preserve policy/friction behavior.
- Existing admin queue and source-health tests still pass.
