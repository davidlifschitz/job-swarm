# Dashboard Resume Rewrite Action Design

Branch: `codex/dashboard-resume-rewrite-action`

## Goal

Make section-level resume rewrite generation reachable from the dashboard so the website supports an actual interactive resume-editing workflow instead of hiding the backend route.

## Problem

`POST /resume/rewrite` already records LLM metadata and creates draft suggestions, and the dashboard can list suggestions. Parsed resume sections are visible, but there is no form to request a rewrite for a section.

## V1 Scope

- Add a compact rewrite form under each parsed resume section.
- Include `section_id`, `target_profile_id`, and explicit `llm_consent`.
- Preserve the existing backend route and suggestion review behavior.
- Redirect successful rewrite requests back to `/dashboard?target_profile_id=...` so the new draft appears immediately.
- Show graceful existing `503` behavior when no rewrite client is configured.

## Safety Boundaries

- The form must make provider consent explicit before sending section text to the configured LLM.
- Accept/reject remains local-only and must not call the LLM.
- Raw resume text may render in the local dashboard because the user uploaded it, but raw prompts, provider internals, and request metadata must not render.

## Acceptance Criteria

- Dashboard renders a rewrite form for each resume section when a target profile is active.
- Posting the dashboard form with consent calls the configured rewrite client and creates a draft suggestion.
- Successful posts redirect back to the target profile dashboard.
- Missing consent and missing rewrite client keep existing failure responses.
- Existing suggestion accept/reject tests continue to pass.

## Later Scope

- Inline text editing before accept.
- Job-specific rewrite suggestions from a selected job detail page.
- Streaming rewrite preview.
