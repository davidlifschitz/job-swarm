# OpenRouter Runtime Client Plan

Spec: `docs/superpowers/specs/2026-05-10-openrouter-runtime-client-design.md`

## Goal

Wire real OpenRouter-backed runtime clients into the web app from environment config while preserving strict tests, consent gates, and metadata safety.

## Ownership

- Controller-owned files:
  - `ml_job_swarm/app.py`
  - new `ml_job_swarm/openrouter.py`
  - `tests/test_openrouter_runtime.py`
  - `README.md`
- No subagent write ownership for this slice because runtime wiring crosses app state and client contracts.

## TDD Steps

1. Add tests for `OpenRouterProvider.complete()`.
   - It posts a chat-completions JSON body with `model`, `messages`, and JSON response format.
   - It parses assistant JSON string content into a dict.
   - It keeps the API key only in the Authorization header.
2. Add tests for `OpenRouterFitGateClient.review_fit()` and `OpenRouterResumeRewriteClient.rewrite_section()`.
   - Each returns schema-shaped JSON from a mocked transport.
   - Prompt bodies include the supplied payload but not the API key.
3. Add tests for `configure_openrouter_clients_from_env()`.
   - Missing key leaves clients disabled.
   - Present key installs all three clients with configured model names.
4. Implement `ml_job_swarm/openrouter.py`.
5. Call the configuration helper from `create_app()`.
6. Add README runtime environment notes.

## Verification

Focused:

```bash
uv run pytest tests/test_openrouter_runtime.py -q
uv run pytest tests/test_routes_onboarding.py tests/test_routes_resume_workspace.py tests/test_llm_contracts.py -q
```

Full:

```bash
uv run pytest
```

## Acceptance Checks

- `create_app()` creates real clients only when `OPENROUTER_API_KEY` exists.
- Existing tests do not make network calls.
- Consent checks remain route-owned and unchanged.
- No secret-like values are persisted in `llm_requests`.

## Review Gates

- `goal-review`: confirm the feature advances real-world web operation without adding unsafe live behavior.
- `test-quality-review`: confirm mocked client tests prove the contract without relying on brittle implementation details.
