# Individual Source Refresh Design

## Goal

Let the local admin refresh one reviewed source from the website so public ATS or
careers pages can be tested without running the whole catalog.

## Scope

V1 adds a `Refresh` action to each enabled source on `/admin/sources`.
The action uses the existing ingestion pipeline and configured adapter registry.
It does not add authenticated scraping, cookies, CAPTCHA bypass, hidden browser
sessions, LinkedIn, or Indeed support.

## Behavior

- `POST /admin/sources/{source_id}/refresh` loads the source from SQLite.
- If the source is missing, return `404`.
- If the source is disabled, return `400` and do not run ingestion.
- If the source type is not registered, redirect to `/admin/runs` with
  `sources_skipped=1` and no ingestion run.
- If supported, call `refresh_source` with the registered adapter.
- Redirect to `/admin/runs` with the same refresh summary fields used by bulk
  refresh.
- `suspicious_empty` counts as completed, not failed, and leaves source friction
  for admin review.

## UI

The existing sources table keeps `Enable` for disabled rows and `Disable` for
enabled rows. Enabled rows also show `Refresh` next to the company name so the
operator can test a single source after editing, approving, or investigating it
without hunting through a wide operational table.

## Tests

- Route test: the source health page renders a visible per-source refresh form.
- Route test: refreshing one supported source inserts jobs, updates
  `last_checked_at`, and redirects to run history with one source refreshed.
- Route test: unsupported source types are skipped without creating failed runs
  or friction events.
- Route test: disabled and missing sources do not run adapters.

## Review Gates

Run goal-review against this spec and implementation. Run focused route tests,
then the full `uv run pytest -q` suite before pushing.
