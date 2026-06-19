# Source Last-Checked Visibility Design

Branch: `claude/fix-website-e2e-Rj73P`

## Goal

Make catalog freshness visible on the admin source health page. Surface the
`job_sources.last_checked_at` timestamp the ingest already records, so admins
can see whether each source has actually been refreshed recently without
digging into the audit log or run history.

## Context

The V1 done criteria spec calls out "daily refresh" for the catalog and
"source health" in the admin UI. The schema already stores
`job_sources.last_checked_at` (set by the ingest run), but
`_source_health_rows` in `ml_job_swarm/app.py` does not select that column,
and `admin_sources.html` has no column for it. From the admin's seat, every
source looks the same — there is no signal of staleness.

## V1 Scope

- Include `last_checked_at` in the `_source_health_rows` SELECT.
- Pass it through to the `sources` list rendered by `admin_sources.html`.
- Add a `Last checked` column to the existing-sources table that shows the
  timestamp, or `Never` if the source has no recorded check.

## Out Of Scope

- No relative-time formatting ("2 days ago"); raw timestamp is enough for V1.
- No staleness alert banner.
- No column for the global "last refresh run" — that already exists at
  `/admin/runs`.
- No sorting or filtering by recency.

## Data And Safety

`last_checked_at` is a local-only timestamp written by the ingest pipeline;
it contains no resume, prompt, or auth data. It is rendered through Jinja
auto-escape.

## TDD And Review Gates

- Add a route test that seeds two sources, one with a known
  `last_checked_at` and one without, and asserts the admin page renders the
  timestamp for the first and `Never` for the second.
- Confirm tests fail before implementation.
- Implement SELECT addition and the new column.
- Run focused tests, then full suite.
