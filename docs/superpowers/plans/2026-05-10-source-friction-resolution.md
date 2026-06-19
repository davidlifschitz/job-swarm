# Source Friction Resolution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add local review/resolution state for source friction events.

**Architecture:** Extend `source_friction_events` with review metadata, add one local admin POST route, reuse sanitization helpers, and render review controls in the existing friction log page.

**Tech Stack:** FastAPI, Jinja, SQLite, pytest, Browser smoke verification.

---

## Files

- Modify: `ml_job_swarm/store.py`
- Modify: `ml_job_swarm/app.py`
- Modify: `ml_job_swarm/web/templates/source_friction.html`
- Modify: `tests/test_store_schema.py`
- Modify: `tests/test_routes_admin_sources.py`

## Task 1: Tests First

- [x] **Step 1: Add failing schema test**

Assert `source_friction_events` contains `review_status`, `reviewed_at`, `reviewed_by`, and `review_note`.

- [x] **Step 2: Add failing route/page tests**

Assert:

- friction page shows `unreviewed` for new events
- POST review updates status, reviewed metadata, and sanitized note
- invalid status returns `400`
- missing event returns `404`
- CSV includes review fields and excludes sensitive note content

- [x] **Step 3: Verify red**

Run:

```bash
uv run pytest tests/test_store_schema.py tests/test_routes_admin_sources.py -q
```

Expected: fail on missing schema columns and route.

## Task 2: Implementation

- [x] **Step 1: Extend schema**

Add columns with defaults to `source_friction_events` in `ml_job_swarm/store.py`.

- [x] **Step 2: Add POST route**

Add `/admin/sources/friction/{event_id}/review`, validate status, sanitize note, update event row, and insert an admin audit event with safe before/after metadata.

- [x] **Step 3: Update friction rows and CSV**

Select review fields in `_friction_export_rows`, sanitize `review_note`, and add CSV headers.

- [x] **Step 4: Update template**

Show review status and note, and add buttons/forms for `reviewed` and `resolved`.

- [x] **Step 5: Verify focused and broad checks**

Run:

```bash
uv run pytest tests/test_store_schema.py tests/test_routes_admin_sources.py -q
uv run pytest -q
```

Expected: all tests pass.

## Task 3: Browser And Publish

- [x] **Step 1: Browser smoke**

Start a local app with one friction event. Open the friction page, submit `reviewed`, and verify the page shows reviewed status without leaking a secret note.

- [x] **Step 2: Review gates**

Run goal-review. Confirm no retry/bypass/source mutation was added.

- [ ] **Step 3: Commit, push, PR, merge**

Commit message:

```bash
git commit -m "Add source friction resolution"
```

Push, create/open PR, merge after verification, then sync `main`.
