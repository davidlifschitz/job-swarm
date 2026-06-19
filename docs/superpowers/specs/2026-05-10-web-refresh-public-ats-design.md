# Web Refresh Public ATS Design

Branch: `codex/web-refresh-public-ats`

## Goal

Make the admin website refresh action perform the same real public-ATS catalog
work as the cron-friendly CLI, instead of attempting unsupported reviewed
sources or hiding the run outcome.

## V1 Scope

- `POST /admin/sources/refresh` uses the configured adapter registry source
  types as an allowlist.
- Reviewed sources whose type is not in that registry are skipped, not treated
  as failures.
- The redirect to `/admin/runs` carries a compact refresh summary:
  sources seen, refreshed, skipped, jobs seen, failures, and blocked.
- `/admin/runs` renders the refresh summary when present.

## Safety Boundary

- Still public ATS only.
- No auth, cookies, CAPTCHA handling, hidden browser sessions, aggregator
  scraping, or autonomous applications.
- Unsupported custom sources remain visible for admin review but are not
  fetched by the public-ATS refresh action.

## Acceptance Criteria

- Admin refresh runs only registry-backed source types.
- Skipped unsupported reviewed sources are counted and visible.
- No friction event is recorded merely because a reviewed source has an
  unsupported source type.
- Existing admin refresh, source, audit, and route tests pass.
- Full test suite passes.
