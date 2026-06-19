# Refresh Diagnostics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show actionable diagnostics for empty public-source refreshes in admin source health.

**Architecture:** Keep the existing `suspicious_empty` status. Add a small details helper in ingestion so all empty adapter results produce consistent friction metadata. The admin source-health page already reads `recommendation` from latest friction details, so route behavior needs only test coverage.

**Tech Stack:** Python ingestion, SQLite friction events, FastAPI route tests.

---

### Task 1: Failing Tests

**Files:**
- Modify: `tests/test_ingest.py`
- Modify: `tests/test_routes_admin_sources.py`

- [ ] Add an ingestion test that empty refresh friction details include `source_type`, `stage`, `reason`, and a useful `recommendation`.
- [ ] Add an admin route test that a per-source empty refresh redirects as completed and then `/admin/sources` shows the diagnostic recommendation.
- [ ] Run focused tests and confirm they fail before implementation.

### Task 2: Diagnostic Details

**Files:**
- Modify: `ml_job_swarm/ingest.py`

- [ ] Add `_empty_result_details(source)` returning consistent metadata.
- [ ] Use it for `empty_suspicious` friction details.
- [ ] Keep existing job preservation and `suspicious_empty` status unchanged.
- [ ] Run focused tests until green.

### Task 3: Verification

**Files:**
- Review changed tests, ingestion, spec, and plan.

- [ ] Run goal-review.
- [ ] Run test-quality-review.
- [ ] Run `uv run pytest tests/test_ingest.py tests/test_routes_admin_sources.py -q`.
- [ ] Run `uv run pytest -q`.
- [ ] Push, open PR, wait for checks, merge, sync main.
