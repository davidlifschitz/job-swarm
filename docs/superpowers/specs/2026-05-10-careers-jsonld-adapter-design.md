# Careers JSON-LD Adapter Design

Branch: `codex/careers-jsonld-adapter`

## Goal

Let user-submitted public employer careers pages produce real job rows when the
page exposes standards-based Schema.org `JobPosting` JSON-LD.

## V1 Scope

- Add a `careers` adapter to the public source registry.
- Fetch only public careers/jobs pages, not arbitrary pages.
- Parse only `<script type="application/ld+json">` payloads.
- Extract nodes whose `@type` includes `JobPosting`, including `@graph`
  payloads.
- Map title, URL, identifier, description, location, remote mode, employment
  type, and requirements into `RawJob`.
- Keep pages without `JobPosting` as empty results so ingestion can mark them
  suspicious-empty for admin review.

## Safety Boundary

- No auth, cookies, CAPTCHA bypass, hidden browser sessions, aggregator search,
  or arbitrary crawling.
- No broad HTML scraping for unstructured job cards in V1.
- The adapter fetches only the submitted reviewed source URL.

## Acceptance Criteria

- Unit tests cover single `JobPosting`, `@graph` payloads, non-job JSON-LD,
  and unsupported non-careers URLs.
- Public source registry includes `careers`.
- Admin `Approve and refresh` can ingest a submitted careers page with JSON-LD.
- Existing ATS and ingestion tests continue passing.
- Full test suite passes.
