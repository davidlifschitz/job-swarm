# Approve Source Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let admins approve a newly submitted public ATS source and immediately ingest jobs from that single source.

**Architecture:** Reuse `review_company_source` for approval and audit logging. After approval, inspect the created `job_sources.source_type`. If the configured adapter registry supports it, call `refresh_source` for that one source. Otherwise redirect to run history with `sources_skipped=1` and no failed ingestion run. Share the admin run-summary redirect helper with the bulk refresh route.

**Tech Stack:** FastAPI routes, Jinja admin template, SQLite, pytest route tests.

---

### Task 1: Queue Action Contract

**Files:**
- Modify: `tests/test_routes_admin_sources.py`
- Modify: `ml_job_swarm/web/templates/admin_sources.html`

- [x] **Step 1: Write failing UI test**

Assert pending queue rows include an `Approve and refresh` form targeting
`/admin/source-review/{queue_id}/approve-refresh`.

- [x] **Step 2: Implement template action**

Add the new form beside the existing approve/reject forms without changing
ordinary approval.

### Task 2: Single Source Refresh

**Files:**
- Modify: `tests/test_routes_admin_sources.py`
- Modify: `ml_job_swarm/app.py`

- [x] **Step 1: Write failing public ATS test**

Approve a Greenhouse queued source with a fake adapter and assert exactly that
source is refreshed, a job is inserted, and the run summary reports one source
and one job.

- [x] **Step 2: Implement route**

Add `POST /admin/source-review/{queue_id}/approve-refresh`, call
`review_company_source`, then `refresh_source` only when the created source
type exists in the adapter registry.

- [x] **Step 3: Write unsupported-source guard**

Assert unsupported approved source types are counted as skipped without a failed
ingestion run or friction event.

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
