# Resume Asset Storage And Vision Payload Plan

Spec: `docs/superpowers/specs/2026-05-10-resume-asset-storage-vision-design.md`

## Goal

Persist uploaded resume files locally and send actual PDF page images to the configured vision provider after explicit consent.

## Ownership

- Controller-owned files:
  - `ml_job_swarm/app.py`
  - `ml_job_swarm/llm.py`
  - `ml_job_swarm/openrouter.py`
  - new `ml_job_swarm/resume_assets.py`
  - `.gitignore`
  - `tests/test_routes_onboarding.py`
  - `tests/test_openrouter_runtime.py`
  - `tests/test_resume_assets.py`

## TDD Steps

1. Add asset storage unit tests.
   - writes bytes under configured directory
   - returns `local://resume-assets/...`
   - rejects traversal and missing files
   - renders PDF page bytes through a monkeypatched renderer seam
2. Add route tests.
   - upload persists a file and storage URI
   - vision fallback sends `private_content_parts` with PDF page image data URI
   - missing stored asset returns failure without consenting the pending run
3. Add OpenRouter provider contract test for multimodal content parts.
4. Implement `resume_assets.py`.
5. Extend `LLMRequest` and `OpenRouterProvider.complete()`.
6. Wire upload and vision fallback routes.

## Verification

Focused:

```bash
uv run pytest tests/test_resume_assets.py tests/test_openrouter_runtime.py tests/test_routes_onboarding.py -q
```

Full:

```bash
uv run pytest
```

## Acceptance Checks

- No raw resume content or base64 image content appears in `llm_requests.response_json`.
- Missing local files do not flip `vision_fallback_status` to `consented`.
- Existing onboarding/preference/dashboard flows continue passing.

## Review Gates

- `goal-review`: confirm this turns vision fallback into real work without unsafe provider calls before consent.
- `test-quality-review`: confirm tests prove storage, route behavior, OpenRouter multimodal payload shape, and privacy boundaries.
