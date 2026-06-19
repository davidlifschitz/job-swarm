# Workable Public Adapter Design

## Goal

Add Workable as a first-class public ATS adapter so reviewed Workable career pages can produce real jobs during dashboard/admin refresh.

## Source Basis

Workable documents a public account endpoint at `https://www.workable.com/api/accounts/{subdomain}` that returns public jobs for an account, with an optional `details` query parameter that includes job descriptions. This is distinct from Workable's authenticated SPI endpoints.

## V1 Scope

- Support reviewed `workable` sources with public URL shapes:
  - `https://apply.workable.com/{subdomain}/`
  - `https://www.workable.com/api/accounts/{subdomain}`
  - `https://{subdomain}.workable.com/...`
- Fetch `https://www.workable.com/api/accounts/{subdomain}?details=true`.
- Parse public job fields into `RawJob`: title, shortcode/code, department, location, remote flag, employment type, seniority, description, apply URL, and source URL.
- Register `workable` in `public_ats_registry()`.
- Reject unsupported Workable URL shapes before network fetch.

## Safety Boundaries

- Public GET-only endpoint; no API key, bearer token, cookies, browser session, CAPTCHA bypass, or hidden session use.
- No LinkedIn, Indeed, search-proxy, or authenticated Workable SPI scraping.
- Malformed payloads create controlled refresh failures through existing ingestion friction handling.

## Acceptance Criteria

- Workable source rows are refreshable from the dashboard/admin routes.
- Unsupported Workable URLs do not trigger network fetches.
- Malformed Workable payloads raise `RefreshError`.
- Registry reports `workable` as a supported public source type.
- Tests use mocked fetchers only.

## Review Gates

- `goal-review`: confirm Workable support advances real public job ingestion without crossing auth or scraping boundaries.
- `test-quality-review`: confirm tests cover parsing, URL support, malformed payloads, and registry inclusion.
