# Normalize Public Careers Seeds Design

## Goal

Ensure every reviewed seed company primary source uses a refreshable adapter type.

## Why This Matters

The public careers adapter now safely fetches static public company career pages, extracts JobPosting JSON-LD, discovers explicit public ATS links, and records suspicious-empty diagnostics. Seed companies still labeled `custom` or `unknown` are skipped by dashboard/admin refresh, so those real public sources never get a chance to produce jobs or friction data.

## V1 Scope

- Convert public company careers URLs currently labeled `custom` or `unknown` to `careers`.
- Keep direct Greenhouse, Ashby, Workday, and other provider labels unchanged.
- Add a catalog guard requiring all seed primary source types to exist in `public_ats_registry`.
- Preserve existing source-policy checks and extra-source validations.

## Safety Boundaries

- Public source-type normalization only.
- No auth, cookies, CAPTCHA handling, hidden browser sessions, LinkedIn, Indeed, search-result scraping, or final submit automation.
- Generic `careers` sources may still return suspicious-empty rather than jobs; that is acceptable because it creates reviewable source-health evidence instead of silent skips.

## Acceptance Criteria

- The seed catalog contains no unsupported primary source types.
- Seed import remains idempotent.
- Admin/dashboard refresh can attempt every reviewed primary source through a supported adapter.
- Unsupported user-submitted sources still go through the review queue and existing policy checks.

## Review Gates

- `goal-review`: confirm this improves real public source operation without inventing provider-specific scraping.
- `test-quality-review`: confirm the catalog guard prevents unsupported seed source drift.
