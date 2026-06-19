# Public Fetch Retry Design

## Goal

Make public ATS refreshes more resilient to transient network read timeouts.

## Scope

The seeded admin refresh now reaches real public ATS and careers endpoints. The
latest smoke left one failure: OpenAI's public Ashby request timed out. This
slice adds a bounded retry inside the default public fetch helpers so a single
transient timeout does not immediately mark a source failed.

This does not add authenticated scraping, cookies, CAPTCHA bypass, hidden
browser sessions, LinkedIn, Indeed, or final submit automation.

## Behavior

- Default JSON, text, and POST JSON fetch helpers retry one transient network
  timeout before raising `RefreshError`.
- Retry is local and bounded; it does not loop indefinitely or hide persistent
  failures.
- Existing error classification remains `blocked_response` if all attempts
  fail.
- Adapter tests use mocked network calls only; no live external request is
  required for deterministic verification.

## Tests

- Public JSON fetcher retries a timeout and returns the successful second
  response.
- Public text fetcher retries a timeout and returns the successful second
  response.
- Public POST JSON fetcher retries a timeout and returns the successful second
  response.
- Existing fetcher header tests and adapter contract tests continue passing.

## Review Gates

Run goal-review and test-quality-review. Run focused public ATS adapter tests
and the full suite.
