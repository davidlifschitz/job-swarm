# Dashboard Operator Console Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve the dashboard, saved jobs, and job detail UI into a cohesive local-first operator console without changing backend behavior.

**Architecture:** Keep route handlers and data models unchanged. Add semantic Jinja wrappers and CSS selectors around existing forms/tables so tests can verify the surface while preserving current actions, consent text, and table row contracts.

**Tech Stack:** FastAPI, Jinja templates, plain CSS, pytest route tests, Browser smoke verification.

---

### Task 1: Dashboard Command Center Contracts

**Files:**
- Modify: `tests/test_routes_app_shell.py`
- Modify: `ml_job_swarm/web/templates/dashboard.html`
- Modify: `ml_job_swarm/web/static/app.css`

- [x] **Step 1: Write failing tests**

Add route assertions that `/dashboard?target_profile_id=...` renders
`dashboard-command-center`, `dashboard-stat-grid`, `Visible matches`,
`Companies`, `Waiting review`, `Fit review`, and command-card classes while
still rendering `dashboard-actions`, `fit-review-action`, `decision-filters`,
and `company-group`.

- [x] **Step 2: Verify red**

Run:

```bash
uv run pytest tests/test_routes_app_shell.py::test_dashboard_renders_operator_console_summary tests/test_routes_app_shell.py::test_dashboard_actions_render_as_command_cards -q
```

Expected: both tests fail because the new classes are not rendered.

- [x] **Step 3: Implement markup and CSS**

In `dashboard.html`, compute visible match counts with a Jinja namespace and add
the command center above the action forms. Wrap each existing action form in a
command card without changing form actions, inputs, labels, buttons, or disabled
conditions. In `app.css`, style the command center, metric cards, command cards,
job rows, and responsive behavior.

- [x] **Step 4: Verify green**

Run:

```bash
uv run pytest tests/test_routes_app_shell.py::test_dashboard_renders_operator_console_summary tests/test_routes_app_shell.py::test_dashboard_actions_render_as_command_cards -q
```

Expected: both tests pass.

### Task 2: Saved Jobs Surface

**Files:**
- Modify: `tests/test_routes_app_shell.py`
- Modify: `ml_job_swarm/web/templates/saved_jobs.html`
- Modify: `ml_job_swarm/web/static/app.css`

- [x] **Step 1: Write failing test**

Assert `/dashboard/saved?target_profile_id=...` renders `page-header`,
`saved-jobs-toolbar`, `saved-jobs-panel`, and `saved-jobs-empty` when no saved
jobs exist.

- [x] **Step 2: Verify red**

Run:

```bash
uv run pytest tests/test_routes_app_shell.py::test_saved_jobs_page_uses_operator_surface -q
```

Expected: fails because the saved-jobs wrapper classes are absent.

- [x] **Step 3: Implement markup and CSS**

Add a page header, toolbar around the existing GET filter form, card list panel
for saved jobs, and empty-state class for no-result states. Preserve all form
names, query params, export URL logic, and decision/application forms.

- [x] **Step 4: Verify green**

Run:

```bash
uv run pytest tests/test_routes_app_shell.py::test_saved_jobs_page_uses_operator_surface -q
```

Expected: the test passes.

### Task 3: Job Detail Surface

**Files:**
- Modify: `tests/test_routes_app_shell.py`
- Modify: `ml_job_swarm/web/templates/job_detail.html`
- Modify: `ml_job_swarm/web/static/app.css`

- [x] **Step 1: Write failing test**

Seed a reviewed job with the existing app-shell helper, request
`/jobs/{job_id}?target_profile_id=...`, and assert `job-detail-shell`,
`job-hero`, `job-detail-grid`, `decision-card`, `application-workspace-card`,
and `local-referrals-card` render.

- [x] **Step 2: Verify red**

Run:

```bash
uv run pytest tests/test_routes_app_shell.py::test_job_detail_page_uses_operator_layout -q
```

Expected: fails because the new detail layout classes are absent.

- [x] **Step 3: Implement markup and CSS**

Wrap the existing detail content in a two-column layout with semantic panels.
Preserve all existing headings, form actions, field names, hidden inputs,
external link attributes, and application/referral behavior.

- [x] **Step 4: Verify green**

Run:

```bash
uv run pytest tests/test_routes_app_shell.py::test_job_detail_page_uses_operator_layout -q
```

Expected: the test passes.

### Task 4: Browser Smoke And Publish

**Files:**
- All changed files.

- [x] **Step 1: Focused tests**

Run:

```bash
uv run pytest tests/test_routes_app_shell.py tests/test_routes_dashboard.py -q
```

Expected: all selected tests pass.

- [x] **Step 2: Browser smoke**

Start:

```bash
ML_JOB_SWARM_DB_PATH=jobs.db ML_JOB_SWARM_SEED_COMPANIES=data/seed_companies.json uv run --with uvicorn uvicorn 'ml_job_swarm.app:create_app_from_env' --factory --host 127.0.0.1 --port 8765
```

Open `/dashboard`, `/dashboard/saved?target_profile_id=1`,
`/jobs/1?target_profile_id=1`, and `/admin/sources` at desktop and mobile
widths. Check that content renders, actions are visible, and text does not
overlap.

- [ ] **Step 3: Publish**

Use `github-push`; prefer `no-mistakes` for push and PR status.
