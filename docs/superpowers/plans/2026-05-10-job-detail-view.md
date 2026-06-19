# Job Detail View Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a profile-scoped job detail page linked from dashboard result groups.

**Architecture:** Keep the page read-only except for existing decision forms. Add one app helper to fetch a job, latest profile-specific fit review, and profile-specific decision notes; add one Jinja template; add dashboard links to the route.

**Tech Stack:** FastAPI, Jinja, SQLite, pytest, Browser smoke verification.

---

## Files

- Modify: `ml_job_swarm/app.py`
- Modify: `ml_job_swarm/web/templates/dashboard.html`
- Create: `ml_job_swarm/web/templates/job_detail.html`
- Modify: `tests/test_routes_onboarding.py`

## Task 1: Tests First

- [x] **Step 1: Add failing tests**

Add route tests that create a profile, company, job, fit review, and optional decision. Tests should assert:

- `/jobs/{job_id}` without `target_profile_id` returns `400`.
- `/jobs/999?target_profile_id={profile_id}` returns `404`.
- `/jobs/{job_id}?target_profile_id={profile_id}` renders title, company, description, requirements, score, label, reasons, risks, apply/source links, notes, and Save/Hide/Clear controls.
- `/dashboard?target_profile_id={profile_id}` links visible, mismatch-risk, and hidden jobs to the detail page.

- [x] **Step 2: Verify red**

Run:

```bash
uv run pytest tests/test_routes_onboarding.py -q
```

Expected: fail on missing route/template links.

## Task 2: Implementation

- [x] **Step 1: Add detail route**

In `ml_job_swarm/app.py`, add:

```python
@app.get("/jobs/{job_id}", response_class=HTMLResponse)
def job_detail(request: Request, job_id: int, target_profile_id: int | None = None) -> HTMLResponse:
    if target_profile_id is None:
        return HTMLResponse("target_profile_id is required", status_code=400)
    detail = _job_detail(conn, job_id, target_profile_id)
    if detail is None:
        return HTMLResponse("Job not found", status_code=404)
    return _render(request, "job_detail.html", job=detail, target_profile_id=target_profile_id)
```

- [x] **Step 2: Add `_job_detail` helper**

Fetch one row joining `jobs` and `companies`, latest `fit_reviews` for the target profile, and optional `job_decisions`. Parse `reasons_json` and `risks_json` with `_safe_json_object` fallback logic for arrays.

- [x] **Step 3: Add template and dashboard links**

Create `job_detail.html` with safe display of all fields and forms that post to `/jobs/{job_id}/decision`. Update dashboard job titles in visible, mismatch-risk, and hidden sections to link to `/jobs/{job_id}?target_profile_id={{ request.query_params.get('target_profile_id') }}`.

- [x] **Step 4: Verify focused and broad checks**

Run:

```bash
uv run pytest tests/test_routes_onboarding.py -q
uv run pytest -q
```

Expected: all tests pass.

## Task 3: Browser And Publish

- [x] **Step 1: Browser smoke**

Start a local app with a seeded job/detail. Open `/jobs/{job_id}?target_profile_id={profile_id}` and verify the title, score, description, and Save/Hide controls render.

- [x] **Step 2: Review gates**

Run goal-review against the finished output. Confirm it is profile-scoped, local-only, and does not introduce live applications or scraping.

- [ ] **Step 3: Commit, push, PR, merge**

Commit message:

```bash
git commit -m "Add job detail view"
```

Push, open a PR, merge after verification, then sync `main`.
