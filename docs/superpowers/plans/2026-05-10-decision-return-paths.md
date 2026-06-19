# Decision Return Paths Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add safe local return paths for job decision forms.

**Architecture:** Keep `record_job_decision` and `clear_job_decision` unchanged. Add a small redirect sanitizer in `ml_job_swarm/app.py`, thread `return_to` through the decision route, and update templates that should remain on their current page.

**Tech Stack:** FastAPI, Jinja, pytest, Browser smoke verification.

---

## Files

- Modify: `ml_job_swarm/app.py`
- Modify: `ml_job_swarm/web/templates/job_detail.html`
- Modify: `ml_job_swarm/web/templates/saved_jobs.html`
- Modify: `tests/test_routes_onboarding.py`

## Task 1: Tests First

- [x] **Step 1: Add failing tests**

Add tests that assert:

- Posting from job detail with `return_to=/jobs/{job_id}?target_profile_id={profile_id}` redirects back to that detail page.
- Posting an unsafe `return_to=https://evil.example` falls back to `/dashboard?target_profile_id=...`.
- Saved shortlist rows render a Clear form and clearing redirects back to `/dashboard/saved?target_profile_id=...`.

- [x] **Step 2: Verify red**

Run:

```bash
uv run pytest tests/test_routes_onboarding.py -q
```

Expected: fail on missing `return_to` behavior and saved-page Clear form.

## Task 2: Implementation

- [x] **Step 1: Add redirect sanitizer**

Add `_safe_return_path(return_to, fallback)` that returns `return_to` only if it starts with `/` and not `//`.

- [x] **Step 2: Update decision route**

Accept `return_to: Annotated[str | None, Form()] = None` and redirect to `_safe_return_path(return_to, fallback)`.

- [x] **Step 3: Update templates**

Add `return_to` hidden fields in `job_detail.html` decision forms. Add a Clear form to `saved_jobs.html` rows with `return_to=/dashboard/saved?target_profile_id=...`.

- [x] **Step 4: Verify focused and broad checks**

Run:

```bash
uv run pytest tests/test_routes_onboarding.py -q
uv run pytest -q
```

Expected: all tests pass.

## Task 3: Browser And Publish

- [x] **Step 1: Browser smoke**

Start a local app with a saved job. Open the saved shortlist, click Clear via form submission, and verify the saved page remains loaded and empty.

- [x] **Step 2: Review gates**

Run goal-review against the finished output. Confirm no external redirect is possible.

- [ ] **Step 3: Commit, push, PR, merge**

Commit message:

```bash
git commit -m "Add safe decision return paths"
```

Push, open a PR, merge after verification, then sync `main`.
