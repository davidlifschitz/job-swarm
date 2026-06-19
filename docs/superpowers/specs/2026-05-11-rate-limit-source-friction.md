# Rate-Limit Source Friction

## Goal

Make source health more actionable by classifying HTTP 429 responses as rate limits instead of generic blocked responses.

## Problem

Live public refreshes can hit temporary rate limits. Treating HTTP 429 as `blocked_response` makes the admin view imply a source is pushing back in the same way as a 403 or hard block. Operators need to know when the right action is to retry later or reduce cadence rather than disable or replace the source.

## V1 Behavior

- Classify HTTP 429 from public JSON, HTML, and POST fetchers as `rate_limited`.
- Preserve the HTTP status code in friction events.
- Record a retry/cadence recommendation for rate-limited refresh failures.
- Surface that recommendation on the admin source health page.

## Review Gates

- `goal-review`: passes if this improves real-world source operation without expanding scraping scope.
- `test-quality-review`: passes if unit, ingestion, and route tests prove classification, storage, and admin visibility.
