# Seed Provider Link Backfill Design

## Goal

Add reviewed direct public provider sources for seed companies whose public careers pages expose stable supported ATS links.

## Why This Matters

Static careers-page discovery makes generic company career pages more useful, but daily refresh is stronger when the seed catalog also stores verified direct provider sources. Direct sources reduce repeated generic-page dependency and make the dashboard/admin source list clearer about which providers are doing real work.

## V1 Scope

- Probe existing `careers` seed companies for explicit static provider links.
- Add only reviewed links that resolve to supported public providers.
- Preserve the company `careers_url` and `ats_type` when the primary page is still the canonical company careers page.
- Verify the direct provider adapters return jobs before adding the source.
- Add catalog tests so extra sources stay allowed and match inferred provider type.

## Backfilled Sources

- Anyscale: `https://jobs.ashbyhq.com/anyscale`
- Hudson River Trading: `https://boards.greenhouse.io/hrttalentcommunity`

## Safety Boundaries

- Public careers pages and public provider APIs only.
- No LinkedIn, Indeed, auth, cookies, CAPTCHA, search-result scraping, hidden browser sessions, or final submit automation.
- No private resume/profile content is involved.

## Acceptance Criteria

- Seed catalog includes the new reviewed extra provider sources.
- Extra seed sources are policy-allowed public provider URLs.
- Extra source `source_type` values match the repository inference rules.
- Seed import remains idempotent.

## Review Gates

- `goal-review`: confirm the data backfill improves real daily refresh without changing compliance boundaries.
- `test-quality-review`: confirm tests protect source-policy and adapter-type correctness.
