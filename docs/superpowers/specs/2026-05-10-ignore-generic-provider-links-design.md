# Ignore Generic Provider Links Design

## Goal

Avoid treating generic provider marketing or documentation links on public careers pages as company job boards.

## Why This Matters

Static provider-link discovery improves real ingestion, but public careers pages can also link to provider marketing pages. A live seed probe found a Greenhouse `job-boards` link that is not a company board. Treating that as a board causes unnecessary provider requests and noisy empty results.

## V1 Scope

- Ignore known generic Greenhouse board slugs discovered from static careers pages.
- Preserve real company board discovery for explicit `boards.greenhouse.io/{company}` links.
- Keep source-policy filtering unchanged.

## Safety Boundaries

- No browser crawling, auth, cookies, CAPTCHA handling, hidden sessions, LinkedIn, Indeed, or search-result scraping.
- This only filters false-positive links before adapter delegation.

## Acceptance Criteria

- Generic Greenhouse `job-boards` links do not call the Greenhouse adapter.
- Real Greenhouse board links still delegate normally.
- Full adapter and repository tests remain green.

## Review Gates

- `goal-review`: confirm the filter reduces false-positive public provider calls without blocking real boards.
- `test-quality-review`: confirm regression and positive delegation tests both cover the change.
