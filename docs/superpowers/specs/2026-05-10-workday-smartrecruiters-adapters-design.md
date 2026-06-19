# Workday And SmartRecruiters Public Adapters Design

## Goal

Expand public ATS refresh coverage so the website can ingest more real employer
job sources instead of skipping source types that are already allowed by policy.

## Scope

V1 adds deterministic adapters for direct public Workday and SmartRecruiters
URLs. It also corrects stale seed metadata where a generic company careers page
was labeled as a specific ATS.

The slice does not add browser scraping, authenticated scraping, cookies,
CAPTCHA bypass, hidden sessions, LinkedIn, Indeed, or final application submit.

## Workday Behavior

`WorkdayAdapter` accepts only `*.myworkdayjobs.com` URLs with a public career
site path, such as `https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite`.
It derives:

- host from the source URL
- tenant from the first host label
- site from the first non-locale path segment

It posts to the public CXS jobs endpoint:

`https://{host}/wday/cxs/{tenant}/{site}/jobs`

with `{"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": ""}`,
then paginates by offset. Each `jobPostings` item becomes a `RawJob` with title,
requisition id, locations text, employment type, and a public job URL.

Generic employer career pages are rejected before fetching.

## SmartRecruiters Behavior

`SmartRecruitersAdapter` accepts only SmartRecruiters-owned public URLs:

- `https://jobs.smartrecruiters.com/{companyIdentifier}`
- `https://careers.smartrecruiters.com/{companyIdentifier}`
- `https://api.smartrecruiters.com/v1/companies/{companyIdentifier}/postings`

It calls the public Posting API list endpoint with `destination=PUBLIC`,
`limit=100`, and offset pagination. It fetches posting details for each id so
description and qualifications are available for matching.

Generic employer career pages are rejected before fetching.

## Seed Corrections

- NVIDIA moves to its direct Workday public board URL.
- Snowflake is no longer labeled Workday because its seeded URL is a generic
  company careers page.
- Block is no longer labeled SmartRecruiters because its seeded URL is a
  generic company careers page.

## Tests

- Workday URL parsing, POST body, pagination, mapping, malformed payload, and
  unsupported URL rejection.
- SmartRecruiters URL parsing, list/detail requests, pagination, mapping,
  malformed payload, and unsupported URL rejection.
- Registry includes `workday` and `smartrecruiters`.
- Seed Workday and SmartRecruiters entries use URLs matching their adapter
  source type.

## Review Gates

Run goal-review and test-quality-review before publishing. Run focused adapter
tests and the full suite.
