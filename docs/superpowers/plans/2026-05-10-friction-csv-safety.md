# Source Friction CSV Safety Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reuse CSV formula neutralization for source friction exports.

**Architecture:** Keep source friction row construction unchanged, then apply `_csv_safe_row` at the CSV writer boundary in `ml_job_swarm/app.py`. Add one route regression test in `tests/test_routes_admin_sources.py`.

**Tech Stack:** FastAPI, SQLite, Python `csv`, pytest.

---

## Files

- Modify: `ml_job_swarm/app.py`
- Modify: `tests/test_routes_admin_sources.py`

## Task 1: Tests First

- [x] **Step 1: Add failing CSV safety test**

Add a route test that seeds a source friction event with a formula-like review note and asserts `/admin/sources/friction.csv` prefixes the exported note with `'` while preserving stored data.

- [x] **Step 2: Verify red**

Run:

```bash
uv run pytest tests/test_routes_admin_sources.py::test_export_friction_csv_neutralizes_spreadsheet_formulas -q
```

Expected: fail because friction CSV currently writes rows without `_csv_safe_row`.

## Task 2: Implementation

- [x] **Step 1: Use CSV safety helper**

Change `/admin/sources/friction.csv` to call `writer.writerow(_csv_safe_row(row))`.

- [x] **Step 2: Verify focused and broad checks**

Run:

```bash
uv run pytest tests/test_routes_admin_sources.py -q
uv run pytest -q
```

Expected: all tests pass.

## Task 3: Publish

- [x] **Step 1: Review gates**

Run goal-review. Confirm this only changes CSV serialization and does not alter stored friction rows.

- [ ] **Step 2: Commit, push, PR, merge**

Commit message:

```bash
git commit -m "Harden source friction CSV export"
```

Push, create/open PR, merge after verification, then sync `main`.
