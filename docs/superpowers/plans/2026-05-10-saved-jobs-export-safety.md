# Saved Jobs Export Safety Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden saved jobs CSV export against cross-profile leakage and spreadsheet formula execution.

**Architecture:** Add route-level regression tests in `tests/test_routes_onboarding.py`. Keep data selection in `saved_job_export_rows`, and add a narrow CSV serialization helper in `ml_job_swarm/app.py` so stored values remain unchanged while exported cells are neutralized.

**Tech Stack:** FastAPI, SQLite, Python `csv`, pytest.

---

## Files

- Modify: `tests/test_routes_onboarding.py`
- Modify: `ml_job_swarm/app.py`

## Task 1: Tests First

- [x] **Step 1: Add failing export safety test**

Add a route test that:

- creates one saved job for profile A with formula-like company, title, and notes values
- creates one saved job for profile B
- calls `/dashboard/saved.csv?target_profile_id=<profile A>`
- asserts the export has one row, omits profile B, and prefixes formula-like exported strings with `'`

- [x] **Step 2: Verify red**

Run:

```bash
uv run pytest tests/test_routes_onboarding.py::test_saved_jobs_export_is_profile_scoped_and_spreadsheet_safe -q
```

Expected: fail because CSV cells currently preserve formula prefixes.

## Task 2: Implementation

- [x] **Step 1: Add CSV safety helpers**

Add `_csv_safe_value(value)` and `_csv_safe_row(row)` in `ml_job_swarm/app.py`.

- [x] **Step 2: Use helpers in CSV export**

Write sanitized rows in `/dashboard/saved.csv` without changing stored database values or HTML rendering.

- [x] **Step 3: Verify focused and broad checks**

Run:

```bash
uv run pytest tests/test_routes_onboarding.py::test_saved_jobs_export_is_profile_scoped_and_spreadsheet_safe -q
uv run pytest tests/test_routes_onboarding.py -q
uv run pytest -q
```

Expected: all tests pass.

## Task 3: Publish

- [x] **Step 1: Review gates**

Run goal-review. Confirm this only affects CSV output, preserves profile scoping, and does not alter stored notes or dashboard HTML.

- [ ] **Step 2: Commit, push, PR, merge**

Commit message:

```bash
git commit -m "Harden saved jobs CSV export"
```

Push, create/open PR, merge after verification, then sync `main`.
