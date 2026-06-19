# Job Detail Privacy Regression Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add regression coverage proving job detail stays narrow and private-data-free.

**Architecture:** Add a single route test in `tests/test_routes_onboarding.py` that seeds adjacent private data and asserts it is not rendered by `/jobs/{job_id}`.

**Tech Stack:** pytest, FastAPI TestClient, SQLite fixtures.

---

## Files

- Modify: `tests/test_routes_onboarding.py`

## Task 1: Regression Test

- [x] **Step 1: Add test**

Create `test_job_detail_does_not_render_adjacent_private_data` near existing job-detail tests.

Seed:

- normal reviewed job and target profile
- private resume section text
- `llm_requests.response_json` containing private prompt/cookie/token sentinels
- `admin_audit_events` containing private sentinel fields
- `source_friction_events.details_json` containing private sentinel fields

Assert public job fields render and all sentinel strings are absent.

- [x] **Step 2: Run focused test**

Run:

```bash
uv run pytest tests/test_routes_onboarding.py -q
```

Expected: pass if route is already narrow; fail only if a leak exists.

## Task 2: Verification And Publish

- [x] **Step 1: Run full suite**

Run:

```bash
uv run pytest -q
```

- [x] **Step 2: Review gates**

Run goal-review and confirm this is regression-only and introduces no new runtime behavior.

- [ ] **Step 3: Commit, push, PR, merge**

Commit message:

```bash
git commit -m "Add job detail privacy regression"
```

Push, create/open PR, merge after verification, then sync `main`.
