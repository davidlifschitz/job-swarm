# Dashboard Catalog Freshness Design

Branch: `claude/fix-website-e2e-Rj73P`

## Goal

Show users when the job catalog was last successfully refreshed by
rendering a small "Catalog refreshed" line at the top of the dashboard.
Without this, users have no signal whether they are looking at jobs from
this morning or last week, and the V1 "daily refresh" promise is invisible
to the people it's meant to serve.

## Context

V1 done criteria includes "Catalog (50 cos, daily refresh)". Loop 2 (PR
#75) surfaced the per-source `last_checked_at` to admins. The user-facing
analogue is a single "Catalog refreshed at <timestamp>" banner on the
dashboard, sourced from the most recent `ingestion_runs` row whose
`status = 'succeeded'`. The schema already records this; the dashboard
route just doesn't read it.

## V1 Scope

- Dashboard route queries the latest `ingestion_runs.finished_at` where
  `status = 'succeeded'`.
- Pass that timestamp into `dashboard.html`.
- Template renders `<p class="catalog-freshness">Catalog refreshed:
  {{ catalog_refreshed_at }} UTC</p>` near the top when a successful run
  exists.
- When no successful run exists, render `<p
  class="catalog-freshness">Catalog has not been refreshed yet.</p>` so
  the user knows the system has not yet ingested.
- Same line shown both in the onboarding-required state and the
  active-profile state.

## Out Of Scope

- No relative time formatting ("3 hours ago"); raw timestamp is enough.
- No staleness color/warning when the timestamp is old.
- No JavaScript.
- No changes to admin pages or to the source-level `Last checked` column
  shipped in PR #75.

## Data And Safety

`finished_at` is a system-controlled UTC timestamp. No user content. The
SELECT runs once per dashboard render; the table is small and indexed by
primary key. Output is Jinja-escaped.

## TDD And Review Gates

- Add a route test that seeds two ingestion runs (an older one and a
  newer one, both `status='succeeded'`) plus a still-running row, then
  GETs `/dashboard?target_profile_id=...` and asserts the rendered HTML
  contains the newer succeeded run's timestamp inside a
  `class="catalog-freshness"` paragraph.
- Add a route test that GETs the dashboard with no ingestion runs at all
  and asserts the "has not been refreshed yet" message renders.
- Add a route test that GETs the empty `/dashboard` (no profile) and
  asserts the freshness line still renders so the user gets context
  before completing onboarding.
- Confirm tests fail before implementation.
- Implement the route + template changes.
- Run focused tests, then the full suite.
