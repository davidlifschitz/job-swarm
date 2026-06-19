# Dashboard Decision Filters Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add view-only dashboard filtering by job decision state.

**Architecture:** Keep `visible_company_results` as the source of company/job grouping, then apply a route-level view filter in `ml_job_swarm/app.py`. Update `dashboard.html` to render query-param filter links and the current decision label.

**Tech Stack:** FastAPI, Jinja, SQLite, pytest, Playwright/Chrome smoke check.

---

## Files

- Modify: `ml_job_swarm/app.py`
- Modify: `ml_job_swarm/web/templates/dashboard.html`
- Modify: `tests/test_routes_onboarding.py`

## Task 1: Tests First

- [x] **Step 1: Add failing route tests**

Add tests that assert:

- `decision_filter=saved` renders saved jobs only and marks the Saved filter active
- `decision_filter=hidden` renders hidden jobs as table rows and hides saved/unmarked rows
- invalid `decision_filter` falls back to all-mode behavior

- [x] **Step 2: Verify red**

Run:

```bash
uv run pytest tests/test_routes_onboarding.py::test_dashboard_filters_saved_jobs_by_decision tests/test_routes_onboarding.py::test_dashboard_filters_hidden_jobs_by_decision tests/test_routes_onboarding.py::test_dashboard_invalid_decision_filter_falls_back_to_all -q
```

Expected: fail because `/dashboard` ignores `decision_filter`.

## Task 2: Implementation

- [x] **Step 1: Add route helpers**

Add `_dashboard_decision_filter(value)` and `_filter_companies_by_decision(companies, decision_filter)` in `ml_job_swarm/app.py`.

- [x] **Step 2: Wire dashboard route**

Accept `decision_filter` on `/dashboard`, normalize it, filter companies before render, and pass `decision_filter` to the template.

- [x] **Step 3: Update dashboard template**

Render filter links for All, Saved, Unmarked, and Hidden. Update the decision label so hidden rows shown in the filtered table read `Hidden`.

- [x] **Step 4: Verify focused, broad, and browser checks**

Run:

```bash
uv run pytest tests/test_routes_onboarding.py -q
uv run pytest -q
```

Then start the app and smoke-check the dashboard filter links in Chrome.

Expected: all tests pass and the dashboard filter UI renders without overlap or missing links.

## Task 3: Publish

- [x] **Step 1: Review gates**

Run goal-review. Confirm this is view-only, V1-scoped, and does not introduce new decision states or LLM behavior.

- [ ] **Step 2: Commit, push, PR, merge**

Commit message:

```bash
git commit -m "Add dashboard decision filters"
```

Push, create/open PR, merge after verification, then sync `main`.
