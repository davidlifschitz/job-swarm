# Dashboard Profile Summary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a local active-profile summary panel to the dashboard.

**Architecture:** Add a small `_profile_summary(conn, target_profile_id)` helper in `ml_job_swarm/app.py`, pass it to `dashboard.html`, and render a compact panel above matches.

**Tech Stack:** FastAPI, Jinja, SQLite, pytest, Browser smoke verification.

---

## Files

- Modify: `ml_job_swarm/app.py`
- Modify: `ml_job_swarm/web/templates/dashboard.html`
- Modify: `tests/test_routes_onboarding.py`

## Task 1: Tests First

- [x] **Step 1: Add failing tests**

Add tests that assert:

- Active dashboard renders `Profile summary`, profile name, version, resume filename, preferences, and latest resume keywords.
- Keywords come from the latest parse run for the active profile's resume asset.
- Dashboard with no `target_profile_id` does not render the panel.
- A profile without keywords renders `No resume keywords captured`.

- [x] **Step 2: Verify red**

Run:

```bash
uv run pytest tests/test_routes_onboarding.py -q
```

Expected: fail on missing profile summary panel.

## Task 2: Implementation

- [x] **Step 1: Add `_profile_summary` helper**

Fetch `target_profiles`, `resume_assets`, and top latest-parse `resume_keywords`. Parse JSON preference columns safely.

- [x] **Step 2: Pass summary to dashboard**

Pass `profile_summary={}` for onboarding and `_profile_summary(...)` for active profile dashboard.

- [x] **Step 3: Render panel**

Add a `profile-summary` section in `dashboard.html` that displays profile fields and keyword chips.

- [x] **Step 4: Verify focused and broad checks**

Run:

```bash
uv run pytest tests/test_routes_onboarding.py -q
uv run pytest -q
```

Expected: all tests pass.

## Task 3: Browser And Publish

- [x] **Step 1: Browser smoke**

Start a local app with a seeded profile and keyword. Open `/dashboard?target_profile_id=...` and verify the profile summary and keyword render.

- [x] **Step 2: Review gates**

Run goal-review. Confirm this only displays local profile metadata and no raw private resume text.

- [ ] **Step 3: Commit, push, PR, merge**

Commit message:

```bash
git commit -m "Add dashboard profile summary"
```

Push, create/open PR, merge after verification, then sync `main`.
