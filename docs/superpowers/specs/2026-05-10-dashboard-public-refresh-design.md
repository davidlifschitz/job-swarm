# Dashboard Public Refresh Design

## Goal

Let the dashboard refresh reviewed public job sources without requiring LLM consent or a configured OpenRouter fit-review client.

## Why This Matters

`Find matches` is useful once OpenRouter is configured, but public source refresh is a separate safe operation. A user should be able to populate real jobs from reviewed public employer/ATS sources first, then decide whether to run private LLM fit review.

## V1 Scope

- Add a dashboard action that refreshes reviewed sources supported by the public adapter registry.
- Do not require `llm_consent` for this refresh-only action.
- Do not require `app.state.fit_gate_client` for this refresh-only action.
- Reuse existing source policy, adapter registry, ingestion runs, snapshots, friction events, and skipped-source counting.
- Redirect back to the dashboard with a refresh summary using the same summary panel fields as match runs.

## Safety Boundaries

- No resume text, profile prompt, or private content leaves the machine during refresh-only.
- No LinkedIn, Indeed, auth-gated pages, cookies, CAPTCHA bypass, hidden browser sessions, or final submit automation.
- Unsupported reviewed sources are counted as skipped, not fetched by a fallback scraper.

## Acceptance Criteria

- Dashboard shows a `Refresh public sources` action for users with a target profile.
- Posting that action refreshes public sources without LLM consent.
- Posting that action works when `fit_gate_client` is unavailable.
- Existing `Find matches` behavior still requires LLM consent and an available fit-review client.
- Tests make no live network or LLM calls.

## Review Gates

- `goal-review`: confirm this advances real-world job discovery without private-provider scope creep.
- `test-quality-review`: confirm route tests cover refresh-only behavior and existing LLM gates.
