# Web Refresh Public ATS Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the website source refresh path match the public-ATS CLI behavior and show the user what happened.

**Architecture:** Keep `refresh_due_sources` as the backend primitive. The web route computes registry-supported source types, counts skipped reviewed sources, calls `refresh_due_sources(..., source_types=registry.source_types())`, then redirects to run history with summary query parameters. `admin_runs.html` renders the summary without storing private request data.

**Tech Stack:** FastAPI, Jinja templates, SQLite, pytest route tests.

---

### Task 1: Route Contract

**Files:**
- Modify: `tests/test_routes_admin_sources.py`
- Modify: `ml_job_swarm/app.py`

- [x] **Step 1: Write failing test**

Assert admin refresh skips reviewed sources whose `source_type` is outside the
adapter registry, refreshes only supported sources, records no friction for the
skipped source, and redirects with a summary.

- [x] **Step 2: Implement route filtering**

Call `refresh_due_sources` with `source_types=app.state.adapter_registry.source_types()`.
Compute skipped reviewed sources before refresh.

- [x] **Step 3: Verify**

Run:

```bash
uv run pytest tests/test_routes_admin_sources.py::test_admin_refresh_sources_filters_to_registry_source_types_and_reports_skips -q
```

### Task 2: Run History Summary

**Files:**
- Modify: `ml_job_swarm/web/templates/admin_runs.html`
- Modify: `ml_job_swarm/web/static/app.css`
- Modify: `tests/test_routes_admin_sources.py`

- [x] **Step 1: Render summary**

Show the refresh summary on `/admin/runs` when query parameters are present.

- [x] **Step 2: Preserve existing admin behavior**

Keep run history, sanitized errors, empty states, and source health links intact.

- [x] **Step 3: Verify**

Run:

```bash
uv run pytest tests/test_routes_admin_sources.py tests/test_routes_app_shell.py -q
```

### Task 3: Review And Publish

- [x] **Step 1: Run review gates**

Use goal-review and test-quality-review against the final diff.

- [x] **Step 2: Verify**

Run:

```bash
uv run pytest -q
```

- [x] **Step 3: Push PR**

Use github-push to commit, push, open the PR, and merge when checks allow.
