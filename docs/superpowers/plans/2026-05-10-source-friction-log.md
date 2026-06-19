# Source Friction Log Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a sanitized local admin friction-log page backed by existing `source_friction_events`.

**Architecture:** Reuse `_friction_export_rows(conn)` as the sanitized data source. Add one FastAPI route, one Jinja template, and one admin-source link.

**Tech Stack:** FastAPI, Jinja, SQLite, pytest, Browser smoke verification.

---

## Files

- Modify: `ml_job_swarm/app.py`
- Modify: `ml_job_swarm/web/templates/admin_sources.html`
- Create: `ml_job_swarm/web/templates/source_friction.html`
- Modify: `tests/test_routes_admin_sources.py`

## Task 1: Tests First

- [x] **Step 1: Add failing tests**

Add tests that assert:

- `/admin/sources` links to `/admin/sources/friction`.
- `/admin/sources/friction` renders an empty state.
- Friction rows render company, source URL, event type, status code, safe details, and created time.
- Sensitive fields are redacted/excluded on the HTML page.
- Existing `/admin/sources/friction.csv` still returns sanitized CSV.

- [x] **Step 2: Verify red**

Run:

```bash
uv run pytest tests/test_routes_admin_sources.py -q
```

Expected: fail on missing friction page route/link.

## Task 2: Implementation

- [x] **Step 1: Add route**

Add `GET /admin/sources/friction` in `ml_job_swarm/app.py` and pass `friction_events=_friction_export_rows(conn)` to `source_friction.html`.

- [x] **Step 2: Add template and link**

Create `source_friction.html` with a table and empty state. Add a link from `admin_sources.html`.

- [x] **Step 3: Verify focused and broad checks**

Run:

```bash
uv run pytest tests/test_routes_admin_sources.py -q
uv run pytest -q
```

Expected: all tests pass.

## Task 3: Browser And Publish

- [x] **Step 1: Browser smoke**

Start a local app with one friction event. Open `/admin/sources/friction` and verify event type, safe details, and no secrets render.

- [x] **Step 2: Review gates**

Run goal-review against the finished output. Confirm it is local-only, sanitized, and does not add scrape bypass behavior.

- [ ] **Step 3: Commit, push, PR, merge**

Commit message:

```bash
git commit -m "Add source friction log"
```

Push, open a PR, merge after verification, then sync `main`.
