# Fit Review Failure UI Design

## Goal

Make dashboard fit review failures safe and understandable when the configured
LLM provider errors.

## Scope

The dashboard can refresh real public jobs and then run the fit gate. Provider
timeouts, transport failures, or invalid provider responses should not bubble
into a generic 500 page. The user should see a controlled failure message, and
the local LLM metadata table should still preserve the failed request status
without raw private prompts.

This does not add new LLM providers, retry OpenRouter requests, send data
without consent, authenticated scraping, cookies, CAPTCHA bypass, LinkedIn,
Indeed, or final submit automation.

## Behavior

- `/dashboard/review-jobs` keeps requiring explicit LLM consent.
- Missing profile and validation errors keep returning 400.
- Provider/runtime failures return a controlled `502` HTML response.
- The response does not include private prompt text, raw resume text, cookies,
  or secrets.
- Existing `llm_requests` failure metadata remains the audit trail.

## Tests

- Route test seeds one reviewable job, configures a fit-gate client that raises,
  posts with consent, and verifies:
  - response status is `502`
  - response contains a safe failure message
  - failed `llm_requests` metadata is recorded
  - private prompt markers do not appear in the response

## Review Gates

Run goal-review and test-quality-review. Run focused dashboard route tests and
the full suite.
