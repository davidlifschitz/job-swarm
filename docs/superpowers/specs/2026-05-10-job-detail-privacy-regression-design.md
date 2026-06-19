# Job Detail Privacy Regression Design

Branch: `codex/job-detail-privacy-regression`

## Goal

Lock down job-detail privacy expectations so `/jobs/{job_id}` cannot accidentally expose adjacent private resume, LLM, audit, or source-friction data.

## Context

The job detail page intentionally shows more job and fit-review context than the dashboard. That makes it worth pinning a regression test around what it does not show: raw resume content, private prompts, cookies, tokens, browser profiles, and source payload details stored in nearby tables.

## V1 Scope

- Add route coverage that seeds private-looking data in resume sections, LLM request metadata, admin audit events, and source friction events.
- Assert job detail renders the expected public job/fit fields.
- Assert private adjacent data is absent from the response body.
- Do not change runtime behavior unless the regression test finds a leak.

## Out Of Scope

- No new UI.
- No new sanitization layer unless required by failing tests.
- No LLM calls.
- No source refresh or application behavior.

## Data And Safety

The job detail route should continue selecting explicit safe columns only. The regression must not require storing real secrets; use sentinel strings only.

## TDD And Review Gates

- Start with a failing-or-proving route test.
- If the route already passes, keep the test as a regression.
- Run focused tests and full suite.
- Run goal-review before publishing.
