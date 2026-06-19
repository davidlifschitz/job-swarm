# OpenRouter Runtime Client Design

Branch: `codex/openrouter-runtime-client`

## Goal

Make the web app able to use real OpenRouter-backed LLM clients from runtime environment configuration instead of requiring tests or callers to inject fake clients.

## Why This Matters

The current web routes can ask for fit review, resume rewrite, and vision fallback, but `create_app()` leaves those clients unset. That keeps the website safe, but it also means the product stops at a stub unless another runner wires clients by hand.

## V1 Scope

- Add a small OpenRouter chat-completions runtime client using the documented `POST /api/v1/chat/completions` shape.
- Configure app state clients from environment variables when `OPENROUTER_API_KEY` is present.
- Keep existing explicit consent gates for private resume content:
  - vision fallback requires the consent route
  - resume rewrite requires `llm_consent=on`
  - fit review requires dashboard LLM consent
- Keep tests mocked. Unit tests must not call OpenRouter live.
- Store existing safe metadata only: model, schema version, request hash, input reference, status, and scrubbed response payload.

## Environment

- `OPENROUTER_API_KEY`: enables runtime OpenRouter clients.
- `OPENROUTER_BASE_URL`: optional override, defaulting to OpenRouter chat completions.
- `OPENROUTER_FIT_MODEL`: optional fit-review model.
- `OPENROUTER_RESUME_REWRITE_MODEL`: optional resume rewrite model.
- `OPENROUTER_VISION_MODEL`: optional vision fallback model.
- `OPENROUTER_HTTP_REFERER`: optional app attribution header.
- `OPENROUTER_APP_TITLE`: optional app attribution header.

If no API key is set, app state stays unset and the current `503` behavior remains.

## Client Contracts

- Fit review client exposes `review_fit(payload)` and returns a JSON object matching `FitGateResponse`.
- Resume rewrite client exposes `rewrite_section(payload)` and returns a JSON object matching `ResumeRewriteResponse`.
- Vision fallback uses the existing `LLMProvider.complete(request)` protocol and returns JSON matching `VisionFallbackResponse`.

## Safety Boundaries

- No API key or bearer token is persisted, logged, or included in request bodies.
- No raw private prompt is written into `llm_requests`.
- Provider failures must return route-level failure responses through existing handlers; they must not create successful fit/rewrite records.
- The runtime client sends private resume-derived content only after the existing route consent checks pass.

## Acceptance Criteria

- With `OPENROUTER_API_KEY` set, `create_app()` installs fit review, resume rewrite, and vision fallback clients.
- Without `OPENROUTER_API_KEY`, `create_app()` preserves existing disabled client behavior.
- Mocked unit tests prove request payload shape, JSON response parsing, error handling, and header handling.
- Existing route tests still pass.
- Full test suite passes without network calls.

## Later Scope

- Model selection UI.
- Per-feature budget controls.
- Live provider smoke tests behind an explicit manual command.
- Vision requests that include rendered page images instead of text-only fallback prompts.
