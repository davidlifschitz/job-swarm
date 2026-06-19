# Web Job Review Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a dashboard action that runs real fit review for open jobs against the active profile.

**Architecture:** Store a fit-gate client on FastAPI app state. Add a consent-gated POST route that calls `review_jobs_for_profile`, then redirects to the dashboard. Render a small dashboard form for the active profile.

**Tech Stack:** FastAPI, Jinja, SQLite, pytest.

---

## Files

- Modify: `ml_job_swarm/app.py`
- Modify: `ml_job_swarm/web/templates/dashboard.html`
- Modify: `tests/test_routes_onboarding.py`

## Task 1: Tests First

- [x] **Step 1: Add failing route tests**

Add tests that assert:

- dashboard renders a `Run fit review` form for an active profile
- missing `llm_consent` returns `400`
- missing `fit_gate_client` returns `503`
- with an injected fake client, `POST /dashboard/review-jobs` creates fit reviews and redirects to the dashboard

- [x] **Step 2: Verify red**

Run:

```bash
uv run pytest tests/test_routes_onboarding.py::test_dashboard_exposes_fit_review_action tests/test_routes_onboarding.py::test_dashboard_review_jobs_requires_llm_consent tests/test_routes_onboarding.py::test_dashboard_review_jobs_requires_fit_gate_client tests/test_dashboard_review_jobs_runs_fit_review_pipeline -q
```

Expected: fail because the form and route do not exist.

## Task 2: Implementation

- [x] **Step 1: Add app state client**

Set `app.state.fit_gate_client = None` in `create_app`.

- [x] **Step 2: Add review route**

Add `POST /dashboard/review-jobs` with form fields `target_profile_id` and `llm_consent`. Call `review_jobs_for_profile(conn, target_profile_id, app.state.fit_gate_client)` on success.

- [x] **Step 3: Add dashboard form**

Render the review action only when onboarding is complete and a target profile is active.

- [x] **Step 4: Verify focused and broad checks**

Run:

```bash
uv run pytest tests/test_routes_onboarding.py -q
uv run pytest -q
```

Expected: all tests pass.

## Task 3: Publish

- [x] **Step 1: Review gates**

Run goal-review. Confirm explicit LLM consent is required and no applications/outreach/live browser actions are performed.

- [ ] **Step 2: Commit, push, PR, merge**

Commit message:

```bash
git commit -m "Add web job review action"
```

Push, create/open PR, merge after verification, then sync `main`.
