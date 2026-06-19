# OpenRouter Transient Retry Implementation Plan

Spec: `docs/superpowers/specs/2026-05-10-openrouter-transient-retry-design.md`

## Goal

Retry one transient OpenRouter timeout before provider-backed web workflows fail.

## Ownership

- Controller-owned files:
  - `ml_job_swarm/openrouter.py`
  - `tests/test_openrouter_runtime.py`
  - this spec and plan pair
- No worker write ownership for this slice because the retry helper sits inside the shared provider transport used by fit review, resume rewrite, and vision fallback.

## TDD Steps

1. Add failing tests in `tests/test_openrouter_runtime.py`.
   - Timeout from `urlopen()` then success.
   - Timeout from `response.read()` then success.
   - HTTP error is not retried.
2. Implement a bounded default transport retry helper in `ml_job_swarm/openrouter.py`.
   - Retry only transient timeout-shaped failures.
   - Preserve current `OpenRouterClientError` messages.
   - Keep all private request data out of error strings.
3. Run focused tests.
4. Run full test suite.

## Acceptance Checks

- One temporary timeout no longer fails a real OpenRouter call.
- Persistent failures still return controlled route-level failures through existing handlers.
- HTTP auth/request errors remain immediate failures.
- Tests make no live network calls.

## Review Gates

- Run `goal-review` before accepting the slice.
- Run `test-quality-review` after tests are written and passing.
