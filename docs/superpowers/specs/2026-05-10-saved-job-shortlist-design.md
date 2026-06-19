# Saved Job Shortlist Design

Branch: `codex/saved-job-shortlist`

## Goal

Add a local saved-jobs page so users can review their saved shortlist in the UI before exporting or applying manually.

## Context

The dashboard already supports saving and hiding jobs, and saved jobs can be exported as CSV. A visible shortlist closes the loop for review workflows: users can scan saved jobs, notes, fit score, recommendations, and open the job detail page without downloading CSV first.

## V1 Scope

- Add `GET /dashboard/saved?target_profile_id=...`.
- Require `target_profile_id`.
- Reuse saved decision data and latest profile-version fit review.
- Show saved jobs ordered by newest decision first.
- Include company, title, fit score, label, recommendation, notes, apply/source links, and detail link.
- Link to the saved page from the main dashboard beside the CSV export link.
- Keep CSV export working.

## Out Of Scope

- No application submission.
- No reminders or calendar integration.
- No external sharing.
- No live source refresh from the saved page.

## Data And Safety

The page reads local SQLite rows only. It must not include resume text or raw LLM prompts. URLs and notes are rendered through Jinja escaping.

## TDD And Review Gates

- Start with route tests for missing profile, empty state, populated saved rows, hidden-job exclusion, and dashboard link.
- Confirm the new tests fail before implementation.
- Implement route, template, and link.
- Run focused tests, full suite, and a browser smoke.
- Run goal-review before publishing.
