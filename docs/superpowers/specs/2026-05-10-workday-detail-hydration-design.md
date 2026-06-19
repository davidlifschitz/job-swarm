# Workday Detail Hydration Design

## Goal

Hydrate Workday jobs with public detail-page JSON so fit review has real job text instead of title/location-only records.

## Why This Matters

Workday list responses are useful for discovering jobs, but they often omit the full job description and requirements. The app can ingest those roles today, yet the downstream rules/LLM fit review has weak input. Fetching the public Workday detail JSON for each listed job improves real matching quality without adding authenticated scraping.

## V1 Scope

- For each Workday list posting with an `externalPath`, fetch the matching public CXS detail URL.
- Merge safe detail fields into the normalized `RawJob`.
- Parse description and requirements-like text when present.
- If detail fetch fails for one job, keep the list-derived job instead of failing the entire source refresh.

## Safety Boundaries

- Public Workday CXS GET only.
- No Workday auth, cookies, CAPTCHA bypass, browser session, hidden session, or final submit automation.
- No private resume/profile content is used during detail hydration.

## Acceptance Criteria

- Workday adapter calls the public detail URL when list postings include `externalPath`.
- Detail text fills `description_text` and `requirements_text`.
- Detail fetch failure gracefully falls back to the list posting.
- Existing pagination and malformed-list behavior remain unchanged.

## Review Gates

- `goal-review`: confirm this improves real public job text without crossing the auth/browser boundary.
- `test-quality-review`: confirm tests cover hydrated and fallback behavior.
