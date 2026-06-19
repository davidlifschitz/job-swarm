# Decision Return Paths Design

Branch: `codex/decision-return-paths`

## Goal

Let job decision forms return to the page where the action was taken, while preventing external or protocol-relative redirects.

## Context

The dashboard, job detail page, and saved shortlist all use the same `POST /jobs/{job_id}/decision` route. The route currently always redirects to the main dashboard, which is fine from dashboard rows but awkward from detail and saved pages. A safe return path improves UX without changing the local decision model.

## V1 Scope

- Add optional `return_to` form field to `POST /jobs/{job_id}/decision`.
- Accept only local absolute paths that start with `/` and do not start with `//`.
- Fall back to `/dashboard?target_profile_id=...` for missing or unsafe return paths.
- Add return-to fields to job detail forms so Save/Hide/Clear return to the detail page.
- Add a Clear form to saved shortlist rows and return to the saved page.

## Out Of Scope

- No external redirects.
- No JavaScript history handling.
- No browser automation or live application actions.
- No changes to decision storage.

## Data And Safety

`return_to` is navigation metadata only. It must never be used for external redirects. Decision notes continue to be stored locally in `job_decisions`.

## TDD And Review Gates

- Start with tests for detail-page redirect, saved-page clear, and unsafe external return fallback.
- Confirm tests fail before implementation.
- Implement the small route/template changes.
- Run focused tests, full suite, and browser smoke.
- Run goal-review before publishing.
