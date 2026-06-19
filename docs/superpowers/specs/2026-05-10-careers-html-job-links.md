# Careers HTML Job Links

Date: 2026-05-10
Branch: `codex/careers-html-job-links`

## Goal

Turn public careers pages that render same-domain job links into real job rows
instead of suspicious-empty friction.

## Evidence

The live refresh reported `empty_suspicious` for Vercel and Stripe even though
their public careers pages render open roles in normal HTML. Browser inspection
confirmed both pages expose same-domain job detail links with role text.

## Scope

- Add a conservative same-domain job-link fallback to the generic careers
  adapter.
- Only accept links on the same host as the reviewed careers page.
- Only accept paths that look like job detail paths under careers/jobs markers.
- Exclude generic links such as "Open Positions", "Read more", and the source
  page itself.
- Keep provider-link delegation and JSON-LD parsing behavior unchanged.

## Out Of Scope

- Browser automation, hidden sessions, login, CAPTCHA, cookies, LinkedIn,
  Indeed, or final application submission.
- Company-specific scraping adapters.
- Guessing department/location from unstructured job cards.

## Acceptance

- Unit tests prove same-domain public job links become `RawJob` rows.
- Vercel and Stripe live-smoke refreshes ingest jobs with no suspicious-empty
  friction.
- Full tests pass.
