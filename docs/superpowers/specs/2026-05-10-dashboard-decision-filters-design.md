# Dashboard Decision Filters Design

Branch: `codex/dashboard-decision-filters`

## Goal

Add dashboard filters so users can scan active profile jobs by decision state without leaving the company-grouped dashboard.

## Context

The dashboard already groups reviewed jobs by company, supports save/hide/clear decisions, keeps hidden jobs collapsed by default, and has a separate saved-jobs page. Users still need a quick way to narrow the dashboard while working through companies.

## V1 Scope

- Add a `decision_filter` query parameter to `/dashboard`.
- Supported values: `all`, `saved`, `unmarked`, `hidden`.
- Invalid values fall back to `all`.
- `all` preserves current behavior: visible jobs stay in the main table, hidden jobs stay under expandable hidden sections, mismatch risks stay collapsed.
- `saved` shows only saved jobs as main rows.
- `unmarked` shows only jobs without a decision as main rows.
- `hidden` shows hidden jobs as main rows so users can restore them in one focused view.
- Render filter links that preserve `target_profile_id` and indicate the active filter.

## Out Of Scope

- No new decision states such as `applied`.
- No saved-jobs page changes.
- No client-side JavaScript filtering.
- No changes to fit scoring, filtering, or LLM review logic.

## Data And Safety

Filtering is view-only. It must not mutate job decisions, target profiles, fit reviews, resume data, LLM metadata, or admin records.

## TDD And Review Gates

- Start with failing dashboard route tests for `saved`, `hidden`, and invalid-filter fallback behavior.
- Implement route-level filtering around the existing `CompanyResult` data.
- Run focused route tests, full suite, and a browser smoke check against a live local app.
- Run goal-review before publishing.
