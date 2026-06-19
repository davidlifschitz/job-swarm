# Resume Suggestion Review Design

Status: approved-for-implementation follow-up slice
Date: 2026-05-10
Branch: `codex/resume-suggestion-review`

## Goal

Make generated resume rewrite suggestions visible and reviewable in the dashboard so the user can accept or reject LLM-written section text without touching raw database rows.

## Product Fit

V1 already supports section-aware resume upload and a backend route that records draft rewrite suggestions. The missing workflow is review: users need to see generated suggestions next to the resume workspace and decide whether to keep them.

## V1 Scope

- Show resume rewrite suggestions for the active `target_profile_id` on `/dashboard`.
- Display section heading/type, suggestion text, status, and timestamp.
- Allow accepting draft suggestions from the dashboard.
- Add rejecting draft suggestions from the dashboard.
- Redirect dashboard-origin accept/reject actions back to the same target profile.

## Non-Goals

- No inline editing in this slice.
- No resume document export.
- No automatic replacement of raw resume sections.
- No new LLM calls while accepting or rejecting.
- No external sync.

## Safety Rules

- Suggestions are local review artifacts.
- Do not expose raw private prompts, request payloads, provider metadata, cookies, tokens, or browser profile data in the suggestion panel.
- Existing explicit consent remains required before `/resume/rewrite` calls the LLM.

## Tests

- dashboard lists draft suggestions for the active profile
- suggestions from another profile are excluded
- accepting from the dashboard updates status and redirects back
- rejecting from the dashboard updates status and redirects back
- reject route returns 404 for missing suggestions

## V2 Options

- inline edit before accept
- generate tailored resume document
- side-by-side diff against original section text
