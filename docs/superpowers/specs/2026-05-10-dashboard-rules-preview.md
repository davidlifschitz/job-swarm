# Dashboard Rules Preview

Date: 2026-05-10
Branch: `codex/rules-preview-dashboard`

## Goal

Make the dashboard useful after public-source refresh even when no OpenRouter
fit-review client is configured.

## Scope

- Add a local rules preview for open, unreviewed jobs.
- Show pass and soft-pass candidates on the dashboard with scores, companies,
  locations, and risks.
- Keep the preview read-only: no LLM calls, no `fit_reviews`, no
  `rules_filter_results`, and no private prompt records.

## Out Of Scope

- Replacing LLM fit review.
- Persisting preview rows.
- Sending resume/profile content to any provider.

## Acceptance

- A matching job appears in rules preview without an LLM client.
- An obvious role/skill mismatch is excluded from the preview.
- Rendering the dashboard does not create fit review, rules, or LLM request rows.
