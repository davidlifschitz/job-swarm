# Resume Asset Storage And Vision Payload Design

Branch: `codex/resume-asset-storage`

## Goal

Make vision fallback capable of extracting from the actual uploaded resume file after consent, instead of sending only a resume asset id to the LLM provider.

## Problem

Resume upload reads bytes, stores a `local://resume-assets/{sha}` URI, then discards the bytes after local parsing. The vision fallback route can now call an OpenRouter provider, but it has no durable resume content to send. A real vision model would receive metadata, not the resume.

## V1 Scope

- Persist uploaded resume bytes to a private local asset directory.
- Store a stable `local://resume-assets/{sha}{suffix}` URI in `resume_assets.storage_path`.
- Add a resolver that can read only files under the configured resume asset directory.
- Add PDF page rendering for vision fallback and attach page images as OpenRouter-compatible `image_url` content parts.
- Extend `LLMRequest` with private multimodal content parts that are hashed for request identity but never persisted raw.
- Keep DOCX local parsing unchanged; DOCX-specific vision/file-parser fallback remains later scope.

## Runtime Config

- `ML_JOB_SWARM_RESUME_ASSET_DIR`: optional private local directory for uploaded resume files.
- Default: `.ml-job-swarm/resume-assets` under the process working directory.
- `.ml-job-swarm/` must stay gitignored.

## Consent And Privacy

- Upload still runs local parsing first.
- Vision fallback sends page images only from `POST /resume/vision-fallback` after the existing pending-consent check.
- `llm_requests` continues to store request hash and input reference only, not image bytes, raw resume text, or private prompts.
- Missing or unreadable local asset files fail the fallback without marking the pending parse run as consented.

## Acceptance Criteria

- Upload writes a durable file and stores a resolvable local URI.
- Duplicate uploads reuse the same hash path.
- Vision fallback provider receives image content parts for PDF resumes after consent.
- Provider request metadata does not persist raw image data or extracted resume text.
- Missing asset file returns a clear error and preserves pending consent state.
- Full tests pass without live network calls.

## Later Scope

- DOCX-to-image rendering or OpenRouter file-parser plugin support.
- Multi-page limits configurable in the UI.
- Encrypted local asset storage.
- User-facing asset deletion controls.
