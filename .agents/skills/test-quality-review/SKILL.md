---
name: test-quality-review
description: Use when reviewing tests, test plans, implementation plans, or completed changes to verify that tests genuinely prove ml-job-swarm product behavior, edge cases, integrations, and safety boundaries.
---

# Test Quality Review

## Purpose

Review whether tests are strong enough to protect the product as it grows. This is not a coverage-percentage review. It checks whether tests would fail for the bugs users actually care about.

## Product Testing Goal

Tests should prove the first-principles workflow:

```text
daily catalog refresh -> source policy -> normalized jobs -> resume/profile extraction -> rules filter -> LLM fit gate -> grouped results -> admin source health
```

## Review Checklist

For each feature or plan, verify tests cover:

- happy path behavior
- invalid inputs and parser failures
- low-confidence resume parse and consented vision fallback
- OpenRouter schema validation, retry, and failure states with mocks
- source-policy blocks for LinkedIn/Indeed, auth-gated pages, CAPTCHA/login, and hidden-session scraping
- daily catalog refresh idempotency, dedupe, stale data, and friction events
- user-added company queue behavior
- rules-first filtering with pass, soft-pass, and reject outcomes
- LLM fit gate labels, 0-100 score, mismatch risks, and current profile version
- grouped company UI behavior, including hidden mismatch-risk sections
- local admin/source-health page behavior and audit events
- privacy guarantees: no raw resume text, cookies, secrets, or private prompt logs in logs

## Test Types Required

- Unit tests for pure logic: source policy, parsing confidence, filtering, scoring schema, dedupe.
- Integration tests for storage flows: ingestion run -> snapshots -> canonical jobs -> fit reviews.
- API/route tests for upload, preferences, dashboard data, admin source health.
- UI smoke tests for first-run wizard, grouped table expansion, resume section selection, admin page.
- Contract tests for OpenRouter request/response schemas using mocked providers.
- Regression fixtures for tricky resumes and job postings.

## Review Method

Return:

1. **Verdict:** `strong`, `adequate with gaps`, or `insufficient`.
2. **Behavior Proven:** what the tests actually prove.
3. **Blind Spots:** bugs that could still ship.
4. **Missing Tests:** concrete tests to add.
5. **Overmocking Risk:** places mocks may hide integration failures.
6. **Decision:** accept, accept with added tests, or block implementation completion.

## Standards

- Prefer tests that verify observable behavior over implementation details.
- Require failing tests before production code for new behavior when practical.
- Mock external LLM/network calls, but assert schemas and stored metadata.
- Use fixtures for resumes, source responses, and job descriptions.
- Do not accept “tested by happy path only” for ingestion, parsing, privacy, or LLM flows.
- Treat flaky browser/workflow tests as a product risk to be fixed, not ignored.

## V2 Parallel Workflow Testing

Keep as a later-phase idea:

- spawn multiple Hermes agents with browser-use against the running local app
- assign each agent an independent workflow: onboarding, resume editing, catalog refresh, grouped results, admin source health, failure recovery
- compare agent findings and screenshots
- use this as adversarial workflow QA after deterministic unit/integration tests are stable

Do not make parallel browser-agent testing a V1 dependency.
