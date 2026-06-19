# Seed ATS Accuracy Design

## Goal

Reduce live refresh failures caused by seed companies that label ordinary
careers pages as direct Greenhouse or Ashby sources.

## Scope

The seed catalog is the first source of truth for real-world refreshes. When a
company page is labeled as a specific ATS, ingestion routes it to that adapter.
The latest seeded bulk refresh showed several generic careers URLs returning
404s through Greenhouse or Ashby public APIs. This slice corrects those
evidence-backed rows so the admin site reports generic careers-page behavior
instead of failed ATS calls.

This does not add authenticated scraping, cookies, CAPTCHA bypass, hidden
browser sessions, LinkedIn, Indeed, or final submit automation.

## Behavior

- Evidence-backed stale Greenhouse and Ashby seed labels become `careers`.
- Direct public ATS adapters remain available for reviewed sources that can
  return real public jobs.
- The generic careers adapter handles company careers pages and records
  suspicious-empty diagnostics when no JobPosting JSON-LD is present.
- The generic careers adapter accepts public `.careers` domains such as
  `github.careers`.
- Existing source-policy blocking stays unchanged.

## Tests

- Seed catalog regression verifies the known live-failing companies are not
  routed through specific ATS adapters.
- Adapter regression verifies `.careers` public domains are eligible for the
  generic careers-page adapter.
- Existing catalog tests continue proving the seed file loads, imports
  idempotently, preserves reviewed source types, and only uses allowed public
  URLs.

## Review Gates

Run goal-review and test-quality-review. Run focused catalog tests, full test
suite, and a seeded admin refresh smoke when practical.
