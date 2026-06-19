# Dashboard Preference Edit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a dashboard preference edit path that uses existing profile
versioning to invalidate stale fit reviews.

**Architecture:** Reuse `update_preferences()` from `profile.py`. Add one
FastAPI POST route and a compact dashboard sidebar form populated from
`profile_summary`.

**Tech Stack:** FastAPI route, Jinja dashboard template, existing SQLite profile
tables.

---

### Task 1: Failing Route/UI Tests

**Files:**
- Modify: `tests/test_routes_dashboard.py`

- [ ] Add a dashboard render test for the edit preferences form.
- [ ] Add a POST route test proving version increments and old reviews are
      hidden after preference update.
- [ ] Run focused tests and confirm they fail before implementation.

### Task 2: Route

**Files:**
- Modify: `ml_job_swarm/app.py`

- [ ] Import `update_preferences`.
- [ ] Add `POST /preferences/{target_profile_id}`.
- [ ] Validate all required preference fields.
- [ ] Redirect to dashboard with `preferences_status=updated`.

### Task 3: Template

**Files:**
- Modify: `ml_job_swarm/web/templates/dashboard.html`
- Modify: `ml_job_swarm/web/static/app.css`

- [ ] Add compact edit form under profile summary.
- [ ] Pre-fill current first preference value for each field.
- [ ] Keep layout responsive.

### Task 4: Verification

**Files:**
- Review changed route, template, CSS, tests, spec, and plan.

- [ ] Run goal-review.
- [ ] Run test-quality-review.
- [ ] Run `uv run pytest tests/test_routes_dashboard.py -q`.
- [ ] Run `uv run pytest -q`.
- [ ] Push, open PR, wait for checks, merge, and sync main.
