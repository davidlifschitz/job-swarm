# Source Review Workflow Implementation Plan

> Use `test-driven-development` for code changes, `goal-review` before accepting the slice, and `test-quality-review` before declaring it complete.

**Goal:** Implement the source-review workflow from `docs/superpowers/specs/2026-05-09-source-review-workflow-design.md`.

## Scope Boundaries

V1 includes queue visibility, approve/reject actions, policy re-checking, and audit rows.

V1 does not include live scraping, auth-gated source support, CAPTCHA bypass, hidden browser sessions, Cloudflare scheduling, or hosted admin auth.

## Files

- Modify: `ml_job_swarm/catalog.py`
- Modify: `ml_job_swarm/app.py`
- Modify: `ml_job_swarm/web/templates/admin_sources.html`
- Modify: `tests/test_catalog.py`
- Modify: `tests/test_routes_admin_sources.py`

## TDD Gates

- [x] Write catalog tests for approve/reject helper behavior.
- [x] Write route tests for queue visibility and approve/reject POSTs.
- [x] Run the focused tests and confirm they fail for missing behavior.
- [x] Implement the smallest catalog/admin changes.
- [x] Run focused tests until green.
- [x] Run full suite.
- [x] Browser-smoke `/admin/sources`.
- [x] Run goal-review and test-quality-review before PR.

## Implementation Steps

1. Add catalog helpers:
   - `review_company_source(conn, queue_id, action, actor="local-admin")`
   - approve path re-runs `classify_source_url`
   - reject path updates status only
   - both paths write `admin_audit_events`

2. Add admin route helpers:
   - `_source_review_rows(conn)`
   - `POST /admin/source-review/{queue_id}/approve`
   - `POST /admin/source-review/{queue_id}/reject`

3. Update admin template:
   - render source review queue above source health
   - show disabled buttons for blocked/reviewed rows
   - preserve existing source health table behavior

4. Verify safety:
   - approving blocked/restricted sources must return an error and must not create `job_sources`
   - audit rows contain status metadata only
   - friction CSV behavior remains sanitized

## Acceptance Checks

- Pending user source appears on `/admin/sources`.
- Approving an allowed pending source creates one normalized company and one job source.
- Re-approving the same queue entry is idempotent enough to avoid duplicate sources.
- Rejecting a source leaves the queue row visible as rejected.
- Existing source-health tests still pass.
