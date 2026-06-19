# Saved Jobs Search And Sort Design

Branch: `codex/saved-jobs-search-sort`

## Goal

Let users search and sort their local saved-job shortlist without changing CSV export behavior.

## Context

The saved jobs page gives a UI shortlist, but it always shows every saved row in recency order. As the shortlist grows, users need quick local filtering by company/title/notes and sorting by score, company, title, or recency.

## V1 Scope

- Add optional query params to `/dashboard/saved`: `q` and `sort`.
- Search saved rows locally by company, title, recommendation, and notes.
- Support sort values: `recent`, `score`, `company`, and `title`.
- Default to `recent`.
- Render a GET filter form that preserves `target_profile_id`.
- Show a distinct empty state when filters match no saved jobs.
- Keep `/dashboard/saved.csv` unchanged.

## Out Of Scope

- No full-text index or database migration.
- No saved-job tags.
- No external sync, outreach, reminders, or application workflow.
- No changes to ingestion or fit review generation.

## Data And Safety

Filtering runs over rows already safe for the saved shortlist. Do not add resume sections, raw prompts, cookies, tokens, browser profiles, or raw source payloads to the page.

## TDD And Review Gates

- Start with route tests for search, no-match empty state, sort by score, sort by company/title, invalid sort fallback, and CSV stability.
- Confirm tests fail before implementation.
- Implement small pure-Python row filtering/sorting helper.
- Run focused tests, full suite, and browser smoke.
- Run goal-review before publishing.
