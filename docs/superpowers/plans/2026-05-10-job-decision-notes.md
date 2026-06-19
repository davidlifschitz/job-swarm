# Job Decision Notes Implementation Plan

> Use `test-driven-development` for code changes, `goal-review` before accepting the slice, and `test-quality-review` before declaring it complete.

**Goal:** Implement local notes for saved/hidden job decisions from `docs/superpowers/specs/2026-05-10-job-decision-notes-design.md`.

## Scope Boundaries

V1 includes local notes display, persistence, and saved CSV export.

V1 does not include reminders, applications, rich editing, external sync, or LLM-generated notes.

## Files

- Modify: `ml_job_swarm/decisions.py`
- Modify: `ml_job_swarm/filtering.py`
- Modify: `ml_job_swarm/app.py`
- Modify: `ml_job_swarm/web/templates/dashboard.html`
- Modify: `tests/test_job_decisions.py`
- Modify: `tests/test_routes_onboarding.py`

## TDD Gates

- [x] Add helper/export tests for notes.
- [x] Add route tests for saving/hiding with notes.
- [x] Add dashboard render tests for notes.
- [x] Run focused tests and confirm missing behavior fails.
- [x] Implement smallest helper/query/route/template changes.
- [x] Run focused tests until green.
- [x] Run full suite.
- [x] Browser-smoke dashboard note rendering.
- [x] Run goal-review and test-quality-review before PR.

## Acceptance Checks

- Notes are visible locally.
- Notes persist across save/hide actions.
- CSV includes saved-job notes.
- Notes are not sent to any LLM or external service.
