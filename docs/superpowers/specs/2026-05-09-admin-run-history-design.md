# Admin Run History Design

Status: approved-for-implementation follow-up slice
Date: 2026-05-09
Branch: `codex/admin-run-history`

## Goal

Expose daily catalog refresh history in the local admin UI so ingestion outcomes are visible before Cloudflare scheduling or hosted deployment work.

## Product Fit

V1 refresh is cron-friendly and records `ingestion_runs`. The operator needs a quick page showing whether the latest refresh succeeded, failed, or saw no sources/jobs.

## V1 Scope

- Add `/admin/runs`.
- Show ingestion run status, start/end time, source count, jobs seen, jobs added, jobs updated, and sanitized error summary.
- Link from `/admin/sources`.
- Keep the page read-only.

## Non-Goals

- No Cloudflare cron setup.
- No live retry button.
- No log streaming.
- No external monitoring.
- No browser-agent scraping diagnostics beyond existing friction events.

## Safety Rules

- Render errors as text, not HTML.
- Do not show secrets, cookies, tokens, raw prompts, resume text, or browser profile data.
- Use the page only for local admin visibility.

## Tests

- empty run history page renders safely
- populated run history page lists latest runs and counts
- admin source page links to run history
- error text is escaped/safe

## V2 Options

- retry failed runs
- Cloudflare cron status
- source-level drilldown per run
- notification hooks
