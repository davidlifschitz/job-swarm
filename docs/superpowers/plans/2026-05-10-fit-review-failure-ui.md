# Fit Review Failure UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent provider/runtime fit-review failures from surfacing as
generic 500 errors in the dashboard.

**Architecture:** Keep `review_jobs_for_profile` as the backend operation that
records failed LLM metadata. Add route-level exception handling around provider
failures in `ml_job_swarm/app.py` and return a small safe HTML error.

**Tech Stack:** FastAPI route, SQLite LLM metadata, route tests.

---

### Task 1: Failing Route Test

**Files:**
- Add: `tests/test_routes_dashboard.py`

- [ ] Seed a target profile and one open job that passes rules.
- [ ] Configure `app.state.fit_gate_client` with a fake client that raises a
      provider/runtime error.
- [ ] POST `/dashboard/review-jobs` with consent.
- [ ] Assert status `502`, safe response text, failed LLM request metadata, and
      no private prompt leakage.
- [ ] Run the focused test and confirm it fails before implementation.

### Task 2: Safe Route Handling

**Files:**
- Modify: `ml_job_swarm/app.py`

- [ ] Catch non-validation provider/runtime failures from
      `review_jobs_for_profile`.
- [ ] Return a safe `502` response that tells the user to retry or check the LLM
      provider configuration.
- [ ] Keep consent, missing profile, unavailable client, and validation behavior
      unchanged.
- [ ] Run focused tests until green.

### Task 3: Verification

**Files:**
- Review changed route, tests, spec, and plan.

- [ ] Run goal-review.
- [ ] Run test-quality-review.
- [ ] Run `uv run pytest tests/test_routes_dashboard.py -q`.
- [ ] Run `uv run pytest -q`.
- [ ] Push, open PR, wait for checks, merge, and sync main.
