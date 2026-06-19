# Web Source Refresh Design

Branch: `codex/web-refresh-sources`

## Goal

Let the admin website trigger the real local job ingestion pipeline instead of only showing source health.

## Context

`refresh_due_sources` already performs the core local work: loads reviewed enabled sources, applies source policy checks, calls source adapters, inserts job snapshots/canonical jobs, updates `last_checked_at`, records ingestion runs, and logs friction. The CLI can use fixture adapters, but the FastAPI website currently has no route or form to run refreshes.

## V1 Scope

- Add `app.state.adapter_registry`, defaulting to an empty registry.
- Add `POST /admin/sources/refresh` that calls `refresh_due_sources(conn, adapter_registry)`.
- Redirect to `/admin/runs` after refresh so the operator sees the new run result.
- Add a refresh form on `/admin/sources`.
- If no adapters are configured, the route should still create failed run/friction entries through existing `refresh_due_sources` behavior instead of crashing.
- Tests inject a fake adapter registry and prove a reviewed source creates jobs and an ingestion run from the web route.

## Out Of Scope

- No live browser scraping.
- No auth/cookie/CAPTCHA bypass.
- No LinkedIn/Indeed aggregation.
- No cron scheduling in this slice.
- No new ATS adapter implementation in this slice.

## Data And Safety

The route only refreshes already-reviewed enabled sources under existing source policy controls. It must not apply to jobs, submit applications, upload resumes externally, or send outreach.

## TDD And Review Gates

- Start with failing admin route tests for refresh form and refresh execution.
- Implement narrow app state and route wiring around existing ingestion code.
- Run focused admin route tests and the full suite.
- Run goal-review before publishing.
