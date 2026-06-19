# Close Stale Public Jobs Design

## Goal

Mark jobs as closed when a supported public source refresh succeeds and previously open jobs from that same source are no longer present.

## Why This Matters

Real public job boards change daily. Without reconciliation, the site keeps showing and reviewing expired postings forever, which makes the dashboard feel like a stub even when source refresh is working. Closing stale jobs keeps grouped results tied to current public listings while preserving historical records locally.

## V1 Scope

- Reconcile stale jobs per `job_source_id` after a successful non-empty refresh.
- Close only jobs that were open for the refreshed source and absent from the latest parsed result set.
- Reopen a previously closed job if it appears again in a later successful refresh.
- Track `jobs_closed` on refresh results, summaries, ingestion runs, CLI output, dashboard summaries, and admin run history.
- Hide closed jobs from grouped fit-review results.

## Safety Boundaries

- Never close jobs after blocked, failed, unsupported, or suspicious-empty refreshes.
- Never use auth, cookies, CAPTCHA handling, hidden sessions, LinkedIn, Indeed, or search-result scraping.
- Do not delete jobs or private user decisions; closure only updates the local `jobs.status`.

## Acceptance Criteria

- Successful non-empty refresh closes missing jobs for that source.
- Reappearing jobs are restored to `open`.
- Failed and suspicious-empty refreshes leave existing jobs open.
- Closed jobs are not shown in dashboard company groups.
- Admin/dashboard/CLI summaries expose a `jobs_closed` count.

## Review Gates

- `goal-review`: confirm this improves real-world catalog freshness without expanding scraping scope.
- `test-quality-review`: confirm tests cover closure, reopening, failure guards, grouped-result filtering, and route/CLI counters.
