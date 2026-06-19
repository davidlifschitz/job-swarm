# Refresh Suspicious Empty Summary Plan

## Tests First

- Add ingest coverage for summary `suspicious_empty`.
- Update CLI summary expectations and add an empty-source case.
- Add dashboard/admin route assertions for the redirect query and rendered label.

## Implementation

- Extend `RefreshSummary` with `suspicious_empty`.
- Increment the count when `RefreshResult.status == "suspicious_empty"`.
- Thread the field through CLI, admin redirects, dashboard redirects, and summary parsing.
- Add template rows for the count.

## Verification

- Run focused tests for ingest, CLI, dashboard, and admin sources.
- Run full pytest before publishing.
