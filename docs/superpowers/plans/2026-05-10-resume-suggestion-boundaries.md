# Resume Suggestion Boundaries Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add profile and status safety boundaries for local resume suggestion review.

**Architecture:** Add route tests in `tests/test_routes_resume_workspace.py`, then update accept/reject routes in `ml_job_swarm/app.py` to use a shared helper that validates profile ownership and updates only draft suggestions.

**Tech Stack:** FastAPI, SQLite, pytest.

---

## Files

- Modify: `ml_job_swarm/app.py`
- Modify: `tests/test_routes_resume_workspace.py`

## Task 1: Tests First

- [x] **Step 1: Add failing tests**

Assert:

- accepting with the wrong `target_profile_id` returns `404` and leaves status `draft`
- accepting an already rejected suggestion leaves it `rejected`
- rejecting an already accepted suggestion leaves it `accepted`
- accept/reject do not create new `llm_requests`

- [x] **Step 2: Verify red**

Run:

```bash
uv run pytest tests/test_routes_resume_workspace.py -q
```

Expected: fail on wrong-profile and terminal-state behavior.

## Task 2: Implementation

- [x] **Step 1: Add helper**

Add `_update_resume_suggestion_status(conn, suggestion_id, status, target_profile_id)` in `app.py`.

- [x] **Step 2: Update routes**

Use the helper in accept/reject. The helper only updates rows whose current status is `draft`; terminal statuses remain unchanged.

- [x] **Step 3: Verify focused and broad checks**

Run:

```bash
uv run pytest tests/test_routes_resume_workspace.py -q
uv run pytest -q
```

Expected: all tests pass.

## Task 3: Publish

- [x] **Step 1: Review gates**

Run goal-review. Confirm there are no LLM calls, no raw resume mutation, and no cross-profile updates.

- [ ] **Step 2: Commit, push, PR, merge**

Commit message:

```bash
git commit -m "Harden resume suggestion review boundaries"
```

Push, create/open PR, merge after verification, then sync `main`.
