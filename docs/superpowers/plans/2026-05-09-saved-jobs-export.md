# Saved Jobs Export Implementation Plan

> Use `test-driven-development` for code changes, `goal-review` before accepting the slice, and `test-quality-review` before declaring it complete.

**Goal:** Implement the saved-job shortlist export from `docs/superpowers/specs/2026-05-09-saved-jobs-export-design.md`.

## Scope Boundaries

V1 includes local CSV export of saved jobs only.

V1 does not include applications, outreach, hosted sync, external spreadsheets, resume export, or LLM calls.

## Files

- Modify: `ml_job_swarm/decisions.py`
- Modify: `ml_job_swarm/app.py`
- Modify: `ml_job_swarm/web/templates/dashboard.html`
- Modify: `tests/test_job_decisions.py`
- Modify: `tests/test_routes_onboarding.py`

## TDD Gates

- [x] Add helper tests for saved-only export rows.
- [x] Add route tests for missing profile and safe CSV output.
- [x] Add dashboard route test for export link visibility.
- [x] Run focused tests and confirm missing behavior fails.
- [x] Implement smallest helper/route/template changes.
- [x] Run focused tests until green.
- [x] Run full suite.
- [x] Browser-smoke dashboard export link.
- [x] Run goal-review and test-quality-review before PR.

## Acceptance Checks

- CSV includes saved jobs for the requested target profile only.
- Hidden and unmarked jobs are absent.
- Export fields are useful for manual follow-up.
- Export excludes private resume text, raw prompts, cookies, tokens, and browser data.
