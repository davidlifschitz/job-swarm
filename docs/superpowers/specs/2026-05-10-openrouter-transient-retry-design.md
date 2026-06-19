# OpenRouter Transient Retry Design

## Goal

Make real OpenRouter-backed fit review, resume rewrite, and vision fallback calls tolerate one transient network timeout before surfacing a provider failure to the web workflow.

## Scope

The web app now wires OpenRouter clients from runtime environment config. First-run matching, resume section rewrite, and vision fallback all depend on those calls once the operator sets `OPENROUTER_API_KEY`. This slice adds a bounded retry around the default urllib transport so one temporary timeout does not make the website feel like a stub.

This does not add automatic application submission, LinkedIn or Indeed scraping, authenticated source access, cookie reuse, CAPTCHA bypass, or hidden browser sessions.

## Behavior

- The default OpenRouter transport retries one transient timeout before failing.
- Transient means a direct `TimeoutError`, a `URLError` whose reason is a `TimeoutError`, or an error message containing `timed out`.
- HTTP responses such as `400` or `401` are not retried because they usually indicate request, auth, quota, or policy failures.
- Retry behavior is local and bounded. Persistent failures still raise `OpenRouterClientError`.
- Errors must not include bearer tokens, private prompts, resume text, or raw request payloads.

## Tests

- Runtime transport retries timeout-then-success and returns the second response.
- Runtime transport retries timeout during response read and returns the second response.
- Runtime transport does not retry HTTP errors.
- Existing OpenRouter request-shape tests continue proving that tokens stay out of request bodies and persisted metadata.

## Review Gates

- `goal-review`: confirm this advances real-world provider operation without weakening consent or compliance boundaries.
- `test-quality-review`: confirm tests exercise retry behavior and non-retry HTTP behavior with mocked network only.
