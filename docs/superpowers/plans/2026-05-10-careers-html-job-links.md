# Careers HTML Job Links Plan

## Tests First

- Add a generic careers adapter test with same-domain `/careers/...` and
  `/jobs/...` anchors.
- Assert generic, cross-domain, and non-HTTP links are ignored.
- Confirm the test fails before implementation.

## Implementation

- Add anchor parsing that returns URL and cleaned anchor text.
- Add a conservative same-domain job-link fallback after JSON-LD and provider
  delegation.
- De-dupe against jobs already found by JSON-LD/provider adapters.
- Use the canonical job URL as apply/source URL and path as external ID.

## Verification

- Run focused adapter tests.
- Run affected adapter/ingest/CLI suites.
- Run full `uv run pytest -q`.
- Run live Vercel/Stripe public refresh smoke and verify jobs are ingested with
  no suspicious-empty friction.
