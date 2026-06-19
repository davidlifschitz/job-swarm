# Dashboard LLM Readiness Design

## Goal

Make dashboard LLM fit-review readiness explicit so users can still refresh public sources while seeing when private fit review is unavailable.

## Why This Matters

The site now performs real public refresh work without OpenRouter. But if OpenRouter is not configured, `Find matches` and `Run fit review` currently look actionable and then fail with a provider-unavailable response. The UI should show that boundary before the user clicks.

## V1 Scope

- Pass fit-review availability into the dashboard template.
- Show a concise readiness message when the fit-review client is unavailable.
- Disable `Find matches` and `Run fit review` buttons when unavailable.
- Keep `Refresh public sources` enabled because it sends no private resume/profile content to an LLM.
- Keep backend route checks unchanged.

## Safety Boundaries

- No private data is sent without explicit consent.
- No fake/demo LLM is added.
- No provider key or environment value is displayed.

## Acceptance Criteria

- Dashboard shows LLM fit-review unavailable state when `fit_gate_client` is unset.
- LLM-dependent buttons are disabled when unavailable.
- Public refresh remains enabled.
- When a fit client is configured, LLM-dependent buttons render normally.
- Existing backend consent/provider gates still pass tests.

## Review Gates

- `goal-review`: confirm this improves real workflow clarity without bypassing provider consent.
- `test-quality-review`: confirm tests cover unavailable and available dashboard states.
