# Saved Jobs CSV Respects Filter Design

Branch: `claude/fix-website-e2e-Rj73P`

## Goal

Make the saved-jobs CSV export honour the search query and sort the user
has applied to the saved jobs page. Today the export always returns every
saved job in default order, regardless of what the user is looking at.

## Context

`/dashboard/saved` already accepts `q` (search) and `sort`
(`recent|score|company|title`) query parameters and passes them through
the in-memory `_filter_saved_jobs` and `_sort_saved_jobs` helpers
(`ml_job_swarm/app.py:462`). The export route
`/dashboard/saved.csv` (`ml_job_swarm/app.py:431`) only takes
`target_profile_id` and emits the full unsorted list. The "Export saved
CSV" link in `saved_jobs.html:6` likewise does not include `q` or `sort`.

The result is a confusing mismatch: a user filtering down to "OpenAI"
saved jobs, sorted by score, clicks Export and gets every saved job in
recent order. CSV escaping safety from PR for plan
`2026-05-10-saved-jobs-export-safety.md` is unchanged by this slice — we
keep the same helper-based escaping and the same fieldnames.

## V1 Scope

- `export_saved_jobs` accepts the same `q` and `sort` query params with
  the same defaults and validation as `saved_jobs`.
- After fetching `saved_job_export_rows`, the route applies
  `_filter_saved_jobs(rows, query)` and `_sort_saved_jobs(..., sort_key)`
  before writing the CSV. CSV row escaping (`_csv_safe_row`) is
  preserved.
- `saved_jobs.html` "Export saved CSV" link includes the current `q` and
  `sort` values when they are set.

## Out Of Scope

- No new sort options.
- No new filter dimensions.
- No JSON export.
- No streaming response — the dataset is small for V1.

## Data And Safety

The `q` value is treated identically to the page request (already
sanitised via `.strip()` in the helper). Unknown `sort` values fall back
to `recent`, mirroring the page route. CSV escaping is unchanged.

## TDD And Review Gates

- Add a route test that seeds three saved jobs (different companies),
  GETs `/dashboard/saved.csv?target_profile_id=...&q=openai&sort=score`,
  and asserts (a) only OpenAI rows appear in the CSV, and (b) they are
  ordered by descending fit_score.
- Add a route test that seeds two saved jobs, GETs the saved page with
  `?q=foo&sort=score`, and asserts the rendered "Export saved CSV" link
  href contains `q=foo` and `sort=score`.
- Add a route test that GETs the export with an unknown sort
  (`?sort=garbage`) and asserts the rows come back ordered by `recent`.
- Confirm tests fail before implementation.
- Implement the route + template changes.
- Run focused tests, then the full suite.
