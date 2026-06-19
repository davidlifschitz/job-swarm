# Public ATS Adapters Design

Branch: `codex/public-ats-adapters`

## Goal

Add real GET-only adapters for public Greenhouse and Lever job boards so website-triggered refresh can fetch live employer/ATS jobs.

## Context

The web admin can now trigger ingestion, but production app state still starts with an empty adapter registry. Greenhouse and Lever both expose public job-posting APIs for published jobs. Greenhouse Job Board API GET endpoints do not require authentication for job-board data, and Lever Postings API returns published postings as JSON via `mode=json`.

## V1 Scope

- Add `GreenhouseAdapter` for `https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true`.
- Add `LeverAdapter` for `https://api.lever.co/v0/postings/{site}?mode=json`.
- Add a `public_ats_registry()` factory returning adapters for `greenhouse` and `lever`.
- Wire `create_app()` to use the public ATS registry by default while still allowing tests to override `app.state.adapter_registry`.
- Parse source URLs from existing reviewed `job_sources.url`.
- Convert public API payloads into `RawJob` records.
- Fail closed with `RefreshError` friction events on bad source URLs, HTTP errors, or malformed payloads.

## Out Of Scope

- No application submission endpoints.
- No auth, cookies, CAPTCHA bypass, hidden browser sessions, LinkedIn, or Indeed.
- No Ashby/Workday/SmartRecruiters adapters in this slice.
- No live network tests; tests mock HTTP fetchers.

## Data And Safety

Adapters only fetch public employer/ATS postings from already-reviewed sources. Source policy still runs before adapter calls. Returned job descriptions may contain HTML; V1 stores cleaned text.

## TDD And Review Gates

- Start with adapter unit tests using fake HTTP fetchers.
- Add a web/default-registry route test proving the admin refresh route can use the default public registry when patched with fake fetchers.
- Run focused adapter/admin tests and the full suite.
- Run goal-review before publishing.

## Source Notes

- Greenhouse Job Board API docs state job-board GET data is public and list jobs supports `content=true`.
- Lever Postings API docs state published jobs are publicly viewable and JSON output is available through `mode=json`.
