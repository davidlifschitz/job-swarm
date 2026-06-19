# Public Ashby Adapter Design

Branch: `codex/public-ashby-adapter`

## Goal

Increase real catalog refresh coverage by supporting Ashby public job boards in the adapter registry.

## Why This Matters

The seed catalog contains multiple `ashby` sources, but the runtime registry currently supports only Greenhouse and Lever. Those sources cannot refresh into jobs without a registered adapter.

## V1 Scope

- Add an `AshbyAdapter` using Ashby's public job postings API:
  - `GET https://api.ashbyhq.com/posting-api/job-board/{JOB_BOARD_NAME}?includeCompensation=false`
- Support native Ashby job board URLs like `https://jobs.ashbyhq.com/{board}`.
- Add a conservative fallback for embedded career pages by deriving the board slug from the host when the source type is already reviewed as `ashby`.
- Parse listed jobs into `RawJob`.
- Register the adapter under `ashby`.
- Use browser-compatible public fetch headers so Ashby does not reject ordinary
  runtime refreshes that are otherwise valid public GETs.

## Safety Boundary

- No authenticated Ashby API.
- No browser sessions, CAPTCHA handling, or hidden scraping.
- No application submission.
- Network access remains GET-only through the existing adapter fetcher seam.

## Acceptance Criteria

- Ashby adapter builds the documented public API URL.
- Default public ATS fetcher sends JSON accept and browser-compatible user-agent
  headers.
- Listed jobs become normalized `RawJob` records.
- Unlisted jobs are skipped.
- Malformed payloads raise `RefreshError`.
- Registry includes `ashby`.
- Full tests pass without live network calls.

## Runtime Smoke

- 2026-05-10: live public fetch for the seeded OpenAI Ashby feed returned a
  valid JSON payload with `apiVersion` and `jobs`.
- 2026-05-10: seeded Ashby source smoke reached valid feeds for 11 of 13
  Ashby-marked companies. The two failures currently resolve as source-catalog
  drift and will create normal source friction events during refresh.

## Source

- Ashby public job postings API: `https://developers.ashbyhq.com/docs/public-job-posting-api`
