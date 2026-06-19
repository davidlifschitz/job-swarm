# First-Run Match Action Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an explicit dashboard action that turns a completed profile plus
reviewed public sources into grouped job matches.

**Architecture:** Reuse `refresh_due_sources()` and `review_jobs_for_profile()`.
Keep admin refresh routes intact. Add one dashboard route, a small query-summary
helper, and a dashboard form.

**Tech Stack:** FastAPI route, Jinja template, SQLite-backed existing refresh
and fit-review services.

---

### Task 1: Failing Route/UI Tests

**Files:**
- Modify: `tests/test_routes_dashboard.py`

- [ ] Add a route test that posts `/dashboard/find-matches`, refreshes one fake
      source, reviews one fake job, redirects with counts, and renders the job
      on dashboard.
- [ ] Add a dashboard empty-state test that the "Find matches" form appears
      for a profile with no current matches.
- [ ] Run focused tests and confirm they fail before implementation.

### Task 2: Route and Summary Helper

**Files:**
- Modify: `ml_job_swarm/app.py`

- [ ] Add `/dashboard/find-matches` with target profile and LLM consent checks.
- [ ] Refresh supported reviewed sources before fit review.
- [ ] Catch validation/provider failures safely.
- [ ] Redirect with match-run query params.
- [ ] Pass parsed match summary to dashboard rendering.

### Task 3: Dashboard UI

**Files:**
- Modify: `ml_job_swarm/web/templates/dashboard.html`
- Modify: `ml_job_swarm/web/static/app.css`

- [ ] Add a "Find matches" form with explicit LLM consent.
- [ ] Render match-run summary counts after redirect.
- [ ] Keep the existing fit-review action available.

### Task 4: Verification

**Files:**
- Review changed route, template, CSS, tests, spec, and plan.

- [ ] Run goal-review.
- [ ] Run test-quality-review.
- [ ] Run `uv run pytest tests/test_routes_dashboard.py -q`.
- [ ] Run `uv run pytest -q`.
- [ ] Run a local Browser smoke for the dashboard action if practical.
- [ ] Push, open PR, wait for checks, merge, and sync main.
