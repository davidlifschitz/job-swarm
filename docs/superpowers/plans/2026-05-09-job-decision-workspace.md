# Job Decision Workspace Implementation Plan

> Use `test-driven-development` for code changes, `goal-review` before accepting the slice, and `test-quality-review` before declaring it complete.

**Goal:** Implement local saved/hidden decisions from `docs/superpowers/specs/2026-05-09-job-decision-workspace-design.md`.

## Scope Boundaries

V1 includes local saved/hidden decisions and reversible dashboard actions.

V1 does not include applications, reminders, outreach, hosted auth, external sync, or LLM-driven decisions.

## Files

- Modify: `ml_job_swarm/store.py`
- Modify: `ml_job_swarm/models.py`
- Create: `ml_job_swarm/decisions.py`
- Modify: `ml_job_swarm/filtering.py`
- Modify: `ml_job_swarm/app.py`
- Modify: `ml_job_swarm/web/templates/dashboard.html`
- Modify: schema/filtering/route tests

## TDD Gates

- [x] Add schema/model tests for `job_decisions`.
- [x] Add decision helper tests for save, hide, clear, invalid decision, and upsert.
- [x] Add filtering tests proving hidden jobs leave visible/mismatch lists and appear under hidden jobs.
- [x] Add route tests proving save/hide/clear POSTs persist and redirect to the same profile dashboard.
- [x] Run focused tests and confirm missing behavior fails.
- [x] Implement smallest code changes.
- [x] Run focused tests until green.
- [x] Run full suite.
- [x] Browser-smoke a dashboard with saved and hidden jobs.
- [x] Run goal-review and test-quality-review before PR.

## Acceptance Checks

- Saving a job shows a saved marker on the dashboard.
- Hiding a job removes it from the normal visible list.
- Hidden jobs remain recoverable under a collapsed company section.
- Clearing a decision restores the job to the correct fit section.
- No private resume text, prompt text, tokens, cookies, or browser data are stored in decisions.
