# Resilient Fit Review Batch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent one per-job fit-review failure from blocking all first-run
matches.

**Architecture:** Add a small result dataclass and resilient batch function in
`filtering.py`. Keep the strict batch function unchanged for existing routes.
Update `/dashboard/find-matches` to use the resilient function and display
`review_failures`.

**Tech Stack:** Python filtering service, FastAPI dashboard route, route/unit
tests.

---

### Task 1: Failing Tests

**Files:**
- Modify: `tests/test_fit_review.py`
- Modify: `tests/test_routes_dashboard.py`

- [x] Add a filtering test where the first job's fit review raises and the
      second job succeeds.
- [x] Add a first-run route test where one reviewed job fails and another is
      displayed.
- [x] Run focused tests and confirm they fail before implementation.

### Task 2: Resilient Batch Function

**Files:**
- Modify: `ml_job_swarm/filtering.py`

- [x] Add a `ProfileReviewBatchResult` dataclass.
- [x] Extract candidate job-id query reuse.
- [x] Add resilient batch review that catches per-job exceptions and continues.
- [x] Preserve strict `review_jobs_for_profile()` behavior.

### Task 3: First-Run Route Counts

**Files:**
- Modify: `ml_job_swarm/app.py`
- Modify: `ml_job_swarm/web/templates/dashboard.html`

- [ ] Use resilient review in `/dashboard/find-matches`.
- [ ] Include `review_failures` in redirect query params and summary panel.
- [ ] Keep provider-unavailable and consent behavior unchanged.

### Task 4: Verification

**Files:**
- Review changed filtering, route, template, tests, spec, and plan.

- [ ] Run goal-review.
- [ ] Run test-quality-review.
- [ ] Run `uv run pytest tests/test_fit_review.py tests/test_routes_dashboard.py -q`.
- [ ] Run `uv run pytest -q`.
- [ ] Push, open PR, wait for checks, merge, and sync main.
