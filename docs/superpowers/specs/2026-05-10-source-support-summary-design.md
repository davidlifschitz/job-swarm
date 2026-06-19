# Source Support Summary Design

## Goal

Show an at-a-glance source coverage summary on the admin source health page.

## Why This Matters

The app can refresh real public ATS sources, but operators still need to scan every row to understand coverage. A simple summary makes it clear how many reviewed sources are refresh-ready, unsupported, or disabled, which helps prioritize adapter work and seed cleanup.

## V1 Scope

- Compute counts from rendered source health rows:
  - total reviewed sources
  - refresh-ready sources
  - unsupported sources
  - disabled sources
- Render the summary above the existing source tables.
- Do not change refresh, approval, source policy, or adapter behavior.

## Safety Boundaries

- Summary is read-only.
- No network requests, scraping, LLM calls, credentials, cookies, or private data access.

## Acceptance Criteria

- `/admin/sources` shows a source coverage summary.
- Counts line up with current adapter support status.
- Existing source row actions and review queue behavior remain unchanged.

## Review Gates

- `goal-review`: confirm this improves operational clarity without scope creep.
- `test-quality-review`: confirm route tests assert meaningful counts and no behavior changes are implied.
