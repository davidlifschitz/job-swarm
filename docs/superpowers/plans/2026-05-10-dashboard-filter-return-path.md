# Dashboard Filter Return Path Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep users on the active dashboard decision filter after decision actions.

**Architecture:** Add one route/template test in `tests/test_routes_onboarding.py`, then update `dashboard.html` to compute the current request path/query once and submit it through existing `return_to` support.

**Tech Stack:** FastAPI, Jinja, pytest.

---

## Files

- Modify: `ml_job_swarm/web/templates/dashboard.html`
- Modify: `tests/test_routes_onboarding.py`

## Task 1: Tests First

- [x] **Step 1: Add failing return path test**

Add a test that renders `/dashboard?target_profile_id=<id>&decision_filter=saved` and asserts job decision forms include `name="return_to"` with the filtered dashboard URL.

- [x] **Step 2: Verify red**

Run:

```bash
uv run pytest tests/test_routes_onboarding.py::test_dashboard_decision_forms_preserve_active_filter_return_path -q
```

Expected: fail because dashboard forms do not submit `return_to`.

## Task 2: Implementation

- [x] **Step 1: Add template return path variable**

Compute `dashboard_return_to` from the current request path and query.

- [x] **Step 2: Add hidden inputs to decision forms**

Add `<input type="hidden" name="return_to" value="{{ dashboard_return_to }}">` to dashboard save, hide, and clear forms.

- [x] **Step 3: Verify focused and broad checks**

Run:

```bash
uv run pytest tests/test_routes_onboarding.py -q
uv run pytest -q
```

Expected: all tests pass.

## Task 3: Publish

- [x] **Step 1: Review gates**

Run goal-review. Confirm this is navigation-only and does not change decision persistence.

- [ ] **Step 2: Commit, push, PR, merge**

Commit message:

```bash
git commit -m "Preserve dashboard filter return paths"
```

Push, create/open PR, merge after verification, then sync `main`.
