# Web Source Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an admin website action that runs the real local source ingestion pipeline.

**Architecture:** Store an adapter registry on the FastAPI app state. Add a POST route that calls `refresh_due_sources` with the app DB connection and registry, then redirects to run history. Render a refresh form on the source health page.

**Tech Stack:** FastAPI, Jinja, SQLite, pytest.

---

## Files

- Modify: `ml_job_swarm/app.py`
- Modify: `ml_job_swarm/web/templates/admin_sources.html`
- Modify: `tests/test_routes_admin_sources.py`

## Task 1: Tests First

- [x] **Step 1: Add failing admin route tests**

Add tests that assert:

- `/admin/sources` renders a form posting to `/admin/sources/refresh`
- `POST /admin/sources/refresh` with an injected adapter registry refreshes reviewed sources, inserts jobs, records an ingestion run, and redirects to `/admin/runs`

- [x] **Step 2: Verify red**

Run:

```bash
uv run pytest tests/test_routes_admin_sources.py::test_admin_sources_page_exposes_refresh_action tests/test_routes_admin_sources.py::test_admin_refresh_sources_runs_ingestion_pipeline -q
```

Expected: fail because the route and form do not exist.

## Task 2: Implementation

- [x] **Step 1: Add app state registry**

Initialize `app.state.adapter_registry = AdapterRegistry({})` in `create_app`.

- [x] **Step 2: Add refresh route**

Add `POST /admin/sources/refresh` that calls `refresh_due_sources(conn, app.state.adapter_registry)` and redirects to `/admin/runs`.

- [x] **Step 3: Add admin form**

Add a source health page form with a clear `Refresh sources` button.

- [x] **Step 4: Verify focused and broad checks**

Run:

```bash
uv run pytest tests/test_routes_admin_sources.py -q
uv run pytest -q
```

Expected: all tests pass.

## Task 3: Publish

- [x] **Step 1: Review gates**

Run goal-review. Confirm this uses reviewed enabled sources only, relies on source policy, and does not perform applications/outreach/live credential work.

- [ ] **Step 2: Commit, push, PR, merge**

Commit message:

```bash
git commit -m "Add web source refresh action"
```

Push, create/open PR, merge after verification, then sync `main`.
