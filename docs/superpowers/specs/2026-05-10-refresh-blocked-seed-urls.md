# Refresh Blocked Seed URLs

Date: 2026-05-10
Branch: `codex/refresh-blocked-seed-urls`

## Goal

Make daily public refresh failures from known-blocking careers pages more
accurate and actionable.

## Evidence

A live public refresh against the reviewed seed catalog recorded hard
`blocked_response` failures for Adept and Citadel Securities. Current public
search/browser evidence shows Adept now publishes careers at
`https://www.adept.ai/about-careers/`, and Citadel Securities publishes careers
at `https://www.citadelsecurities.com/careers/`.

## Scope

- Update the two reviewed seed URLs.
- Keep both rows routed through the generic public careers adapter.
- Add a catalog regression for the corrected URLs.
- Accept public careers slugs such as `about-careers`.
- Preserve HTTP status codes from public fetch failures in source friction rows.

## Out Of Scope

- Authenticated scraping, cookies, CAPTCHA handling, hidden browser sessions, or
  browser-only scraping.
- Changing cron exit semantics.
- Adding source-specific adapters for these companies.

## Acceptance

- Catalog tests lock the corrected URLs.
- A public refresh of the two-source subset records `blocked_response` events
  with `status_code=403` for sites that reject the public cron fetcher.
- Full tests pass.
