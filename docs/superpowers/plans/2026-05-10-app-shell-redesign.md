# App Shell Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the Jinja website into a polished operational app shell without changing core behavior.

**Architecture:** Preserve current route contracts and test-dependent classes. Add semantic wrapper classes to `base.html` and `dashboard.html`, then replace `app.css` with a cohesive product UI system covering nav, panels, tables, forms, status chips, and responsive layout.

**Tech Stack:** FastAPI, Jinja templates, plain CSS, pytest route tests, Browser smoke verification.

---

### Task 1: Shell Contracts

**Files:**
- Create: `tests/test_routes_app_shell.py`
- Modify: `ml_job_swarm/web/templates/base.html`

- [x] **Step 1: Write failing shell tests**

Assert `/onboarding` renders `class="app-shell"`, `class="app-sidebar"`,
`class="app-content"`, `class="local-status"`, and still renders
`class="global-nav"` plus the existing active link.

- [x] **Step 2: Implement shell wrappers**

Wrap the existing primary nav and `main.page` with shell elements. Do not remove
existing `global-nav`, `page`, `flash`, route URLs, or `aria-current`.

- [x] **Step 3: Verify**

Run:

```bash
uv run pytest tests/test_routes_app_shell.py tests/test_routes_onboarding.py::test_onboarding_page_renders_global_nav_with_active_link -q
```

### Task 2: Dashboard Layout Contracts

**Files:**
- Modify: `tests/test_routes_app_shell.py`
- Modify: `ml_job_swarm/web/templates/dashboard.html`

- [x] **Step 1: Write failing dashboard layout test**

Seed a minimal reviewed job/profile using existing route-test helpers or simple
database inserts. Assert `/dashboard?target_profile_id=...` renders
`dashboard-shell`, `dashboard-actions`, `dashboard-primary`, and
`dashboard-sidebar` while preserving `fit-review-action`, `decision-filters`,
and `company-group`.

- [x] **Step 2: Add dashboard wrappers**

Add page-header/action/sidebar wrappers around existing blocks. Do not rename
forms, links, `data-section-id`, `job-row`, `company-group`, or decision
classes.

- [x] **Step 3: Verify**

Run:

```bash
uv run pytest tests/test_routes_app_shell.py tests/test_routes_onboarding.py tests/test_routes_resume_workspace.py -q
```

### Task 3: CSS System

**Files:**
- Modify: `ml_job_swarm/web/static/app.css`
- Modify: `ml_job_swarm/web/templates/admin_sources.html`
- Modify: `tests/test_routes_app_shell.py`

- [x] **Step 1: Replace styling**

Implement:

- left app shell
- compact status bar
- panel/table/form/button system
- job score/status badges
- admin source-health action bar and framed tables
- responsive single-column mobile layout
- no decorative blobs, oversized heroes, or nested card styling

- [x] **Step 2: Verify CSS contracts**

Add route/static assertions for important class selectors in
`tests/test_routes_app_shell.py`.

- [x] **Step 3: Browser smoke**

Start the app with a temporary seeded database, open `/onboarding`,
`/dashboard`, and `/admin/sources`, and inspect screenshots at desktop and
mobile widths for overlap and usability.

### Task 4: Review And Publish

**Files:**
- All changed files.

- [x] **Step 1: Run review gates**

Run `goal-review` and `test-quality-review` against the final diff.

- [x] **Step 2: Verify**

Run:

```bash
uv run pytest
```

- [x] **Step 3: Push PR**

Use `github-push` to commit, push, open the PR, wait for checks, and merge if
checks pass.
