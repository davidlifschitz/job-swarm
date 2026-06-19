# Resume Suggestion Review Implementation Plan

> Use `test-driven-development` for code changes, `goal-review` before accepting the slice, and `test-quality-review` before declaring it complete.

**Goal:** Implement dashboard review for generated resume rewrite suggestions from `docs/superpowers/specs/2026-05-10-resume-suggestion-review-design.md`.

## Scope Boundaries

V1 includes listing suggestions and accepting/rejecting draft suggestions locally.

V1 does not include inline editing, resume export, automatic section replacement, new LLM calls, or external sync.

## Files

- Modify: `ml_job_swarm/app.py`
- Modify: `ml_job_swarm/web/templates/dashboard.html`
- Modify: `tests/test_routes_resume_workspace.py`

## TDD Gates

- [x] Add route tests for dashboard suggestion listing and profile scoping.
- [x] Add route tests for accept/reject dashboard redirects.
- [x] Add missing-suggestion reject test.
- [x] Run focused tests and confirm missing behavior fails.
- [x] Implement smallest app/template changes.
- [x] Run focused tests until green.
- [x] Run full suite.
- [x] Browser-smoke dashboard suggestion panel.
- [x] Run goal-review and test-quality-review before PR.

## Acceptance Checks

- Suggestions are visible without SQLite access.
- Only the active profile's suggestions are shown.
- Accept/reject changes are durable in SQLite.
- No raw private prompts or provider metadata are rendered in the panel.
