# Web Job Review Design

Branch: `codex/web-review-jobs`

## Goal

Let the dashboard trigger real local fit review for open jobs against the active target profile.

## Context

Job ingestion can now be triggered from the admin site, but the dashboard still only displays existing fit reviews. The backend already has `review_jobs_for_profile`, which runs deterministic rules and LLM fit-gate review for unreviewed open jobs. The website needs an explicit operator action to run that workflow.

## V1 Scope

- Add `app.state.fit_gate_client`, defaulting to `None`.
- Add `POST /dashboard/review-jobs` with required `target_profile_id` and `llm_consent`.
- If no fit-gate client is configured, return `503`.
- If consent is missing, return `400`.
- On success, call `review_jobs_for_profile`, then redirect to the active dashboard.
- Render a dashboard form that asks for explicit fit-review consent before posting.
- Tests inject a fake fit-gate client and prove the route creates fit reviews and visible matches.

## Out Of Scope

- No live OpenRouter client implementation in this slice.
- No automatic review during onboarding.
- No application submission or outreach.
- No review of hidden/closed jobs beyond existing backend selection rules.

## Data And Safety

Fit review can send job/profile content to the configured LLM provider. The route must require explicit consent, use existing `llm_requests` metadata storage, and avoid raw private prompt logs.

## TDD And Review Gates

- Start with failing route tests for missing consent, missing client, and successful review.
- Implement narrow route/state/template wiring.
- Run focused dashboard route tests and the full suite.
- Run goal-review before publishing.
