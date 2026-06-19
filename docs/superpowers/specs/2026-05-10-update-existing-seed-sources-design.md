# Update Existing Seed Sources Design

## Goal

Make seed catalog import update reviewed metadata for existing companies and sources, not only insert missing rows.

## Why This Matters

Seed catalog fixes are only useful for users with existing `jobs.db` files if the importer refreshes metadata already in SQLite. Without this, old `custom` or `unknown` source types can remain in the local database forever, so dashboard/admin refresh still skips public careers sources even after the seed JSON is corrected.

## V1 Scope

- Keep `imported_companies` counting only newly inserted companies.
- Update existing seeded company metadata on import:
  - aliases
  - categories/tags
  - stage
  - priority tier
  - primary careers URL
  - primary ATS/source type
  - reviewed source quality
- Update existing reviewed job source rows for matching company and URL:
  - source type
  - policy mode
  - review status
- Preserve existing source-policy rejection for blocked seed URLs.

## Safety Boundaries

- Local SQLite metadata update only.
- No live scraping, auth, cookies, CAPTCHA handling, hidden browser sessions, LinkedIn, Indeed, search-result scraping, or final submit automation.
- Does not delete user-added sources or private user data.

## Acceptance Criteria

- Re-importing a corrected seed file updates existing company and job-source metadata.
- Import remains idempotent for inserted-company counts.
- Blocked seed sources are still rejected before any DB mutation is committed.
- Full catalog and repository tests pass.

## Review Gates

- `goal-review`: confirm this makes corrected seed decisions durable in existing local databases.
- `test-quality-review`: confirm tests cover stale metadata update without weakening idempotency.
