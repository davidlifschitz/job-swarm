# Admin Audit Value Redaction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redact sensitive-looking JSON string values in admin audit and source friction presentation/export paths.

**Architecture:** Reuse the existing `_sanitize_details` boundary in `ml_job_swarm/app.py`. Add tests in `tests/test_routes_admin_sources.py` that prove sensitive values under safe keys are redacted while safe values remain visible.

**Tech Stack:** FastAPI, SQLite, Python `csv`, pytest.

---

## Files

- Modify: `ml_job_swarm/app.py`
- Modify: `tests/test_routes_admin_sources.py`

## Task 1: Tests First

- [x] **Step 1: Add failing redaction tests**

Add tests that assert:

- `/admin/audit` redacts sensitive-looking string values under safe keys
- `/admin/sources/friction.csv` redacts sensitive-looking `details_json` string values under safe keys
- safe values remain visible

- [x] **Step 2: Verify red**

Run:

```bash
uv run pytest tests/test_routes_admin_sources.py::test_admin_audit_page_redacts_sensitive_values_under_safe_keys tests/test_routes_admin_sources.py::test_source_friction_csv_redacts_sensitive_values_under_safe_keys -q
```

Expected: fail because `_sanitize_details` currently strips sensitive keys but leaves string values unchanged.

## Task 2: Implementation

- [x] **Step 1: Sanitize string values**

Update `_sanitize_details` so string values pass through `_sanitize_error_text`.

- [x] **Step 2: Verify focused and broad checks**

Run:

```bash
uv run pytest tests/test_routes_admin_sources.py -q
uv run pytest -q
```

Expected: all tests pass.

## Task 3: Publish

- [x] **Step 1: Review gates**

Run goal-review. Confirm this is presentation/export redaction only and does not change stored audit/friction rows.

- [ ] **Step 2: Commit, push, PR, merge**

Commit message:

```bash
git commit -m "Redact sensitive admin audit values"
```

Push, create/open PR, merge after verification, then sync `main`.
