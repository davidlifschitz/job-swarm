# Refresh Diagnostics Design

## Goal

Make empty public-source refreshes actionable in admin source health.

## Scope

When an adapter returns zero jobs, ingestion still preserves existing open jobs
and records `empty_suspicious`. This slice enriches the friction details with a
source type, stage, and recommendation so `/admin/sources` can show a useful
next step instead of generic manual review.

This does not add new source fetching, browser scraping, authenticated scraping,
cookies, CAPTCHA bypass, LinkedIn, Indeed, or final submit automation.

## Behavior

- Empty refresh friction includes:
  - `reason: adapter_returned_zero_jobs`
  - `stage: fetch_jobs`
  - `source_type`
  - `recommendation`
- `careers` sources recommend checking whether the page exposes JobPosting
  JSON-LD or needs a source-specific adapter.
- registered ATS sources recommend checking whether the public board is empty,
  stale, or has changed its public API shape.
- unsupported/custom sources keep the existing skip behavior outside ingestion.

## Tests

- Ingestion test verifies empty friction details include source type, stage, and
  recommendation while preserving existing jobs.
- Route test verifies admin source health displays the empty diagnostic
  recommendation after a per-source empty refresh.

## Review Gates

Run goal-review and test-quality-review. Run focused ingestion/admin route tests
and the full suite.
