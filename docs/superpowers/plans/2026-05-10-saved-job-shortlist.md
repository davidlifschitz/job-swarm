# Saved Job Shortlist Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a local saved-job shortlist page backed by existing job decisions.

**Architecture:** Reuse `saved_job_export_rows` as the data source, adding `job_id` for detail links while keeping CSV output stable. Add one FastAPI route, one Jinja template, and one dashboard link.

**Tech Stack:** FastAPI, Jinja, SQLite, pytest, Browser smoke verification.

---

## Files

- Modify: `ml_job_swarm/decisions.py`
- Modify: `ml_job_swarm/app.py`
- Modify: `ml_job_swarm/web/templates/dashboard.html`
- Create: `ml_job_swarm/web/templates/saved_jobs.html`
- Modify: `tests/test_routes_onboarding.py`

## Task 1: Tests First

- [x] **Step 1: Add failing tests**

Add tests that assert:

- `/dashboard/saved` without `target_profile_id` returns `400`.
- Empty saved shortlist renders an empty state.
- Saved rows render company, title, score, label, recommendation, notes, apply/source URLs, and detail link.
- Hidden jobs do not appear.
- Main dashboard links to `/dashboard/saved?target_profile_id=...`.

- [x] **Step 2: Verify red**

Run:

```bash
uv run pytest tests/test_routes_onboarding.py -q
```

Expected: fail on missing route/template/link.

## Task 2: Implementation

- [x] **Step 1: Add `job_id` to saved rows**

Select `jobs.id AS job_id` in `saved_job_export_rows`. Update CSV writer creation with `extrasaction="ignore"` so the extra UI field does not change CSV columns.

- [x] **Step 2: Add saved page route**

Add `GET /dashboard/saved` in `ml_job_swarm/app.py`; require target profile, catch `ValueError`, and render `saved_jobs.html`.

- [x] **Step 3: Add template and dashboard link**

Create `saved_jobs.html` with empty state and rows. Add a dashboard link next to the saved CSV export link.

- [x] **Step 4: Verify focused and broad checks**

Run:

```bash
uv run pytest tests/test_routes_onboarding.py -q
uv run pytest -q
```

Expected: all tests pass.

## Task 3: Browser And Publish

- [x] **Step 1: Browser smoke**

Start a local app with one saved job. Open `/dashboard/saved?target_profile_id=...` and verify the saved job, note, and detail link render.

- [x] **Step 2: Review gates**

Run goal-review against the finished output. Confirm it is local-only and does not include private resume text.

- [ ] **Step 3: Commit, push, PR, merge**

Commit message:

```bash
git commit -m "Add saved job shortlist"
```

Push, open a PR, merge after verification, then sync `main`.
