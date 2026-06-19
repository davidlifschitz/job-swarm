# Resume Suggestion Boundaries Design

Branch: `codex/resume-suggestion-boundaries`

## Goal

Harden resume suggestion review so accept/reject actions are profile-scoped, status-safe, and never create new LLM requests.

## Context

V1 supports generating draft resume suggestions through explicit LLM consent, then accepting or rejecting those suggestions locally. The current happy path is covered, but review boundaries should be explicit before the resume workspace grows more interactive.

## V1 Scope

- Accept/reject actions must validate `target_profile_id` when provided.
- A dashboard-origin action for the wrong profile should return `404` and leave the suggestion unchanged.
- Accepting an already rejected suggestion should not mutate it.
- Rejecting an already accepted suggestion should not mutate it.
- Accept/reject must not create any new `llm_requests` rows.
- Existing no-profile direct accept/reject behavior remains supported for local tests/manual use.

## Out Of Scope

- No new LLM calls.
- No suggestion editing UI.
- No resume designer.
- No external sharing or hosted auth.

## Data And Safety

Suggestion review changes only `resume_rewrite_suggestions.status`. It must not alter raw resume sections, write prompt logs, or expose private resume text.

## TDD And Review Gates

- Start with failing route tests for wrong-profile and terminal-state transitions.
- Implement narrow status/profile guards.
- Run focused tests and full suite.
- Run goal-review before publishing.
