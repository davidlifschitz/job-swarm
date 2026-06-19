# Saved Jobs Search And Sort Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add query-param search and sort to the local saved jobs page.

**Architecture:** Keep `saved_job_export_rows` unchanged for CSV/source rows. Add `_filter_saved_jobs` and `_sort_saved_jobs` helpers in `ml_job_swarm/app.py`, pass query state to the Jinja template, and render a GET form.

**Tech Stack:** FastAPI, Jinja, pytest, Browser smoke verification.

---

## Files

- Modify: `ml_job_swarm/app.py`
- Modify: `ml_job_swarm/web/templates/saved_jobs.html`
- Modify: `tests/test_routes_onboarding.py`

## Task 1: Tests First

- [x] **Step 1: Add failing route tests**

Assert:

- `q=alpha` only shows saved rows whose company/title/recommendation/notes contain alpha.
- no-match search shows `No saved jobs match your filters`.
- `sort=score` orders higher score first.
- `sort=company` and `sort=title` order alphabetically.
- invalid `sort` falls back to `recent`.
- CSV export remains unfiltered and unchanged.

- [x] **Step 2: Verify red**

Run:

```bash
uv run pytest tests/test_routes_onboarding.py -q
```

Expected: fail on missing filtering/sorting/form behavior.

## Task 2: Implementation

- [x] **Step 1: Add helper functions**

Add `_filter_saved_jobs(rows, query)` and `_sort_saved_jobs(rows, sort_key)` in `app.py`.

- [x] **Step 2: Update route**

Accept `q` and `sort`, apply filter and sort, and pass `query`, `sort`, `has_filters`, and `sort_options` to the template.

- [x] **Step 3: Update template**

Add a compact GET form. Preserve `target_profile_id`, render selected sort option, and distinguish empty saved list from no filtered matches.

- [x] **Step 4: Verify focused and broad checks**

Run:

```bash
uv run pytest tests/test_routes_onboarding.py -q
uv run pytest -q
```

Expected: all tests pass.

## Task 3: Browser And Publish

- [x] **Step 1: Browser smoke**

Start a local app with two saved rows. Open `/dashboard/saved?q=alpha&sort=score&target_profile_id=...` and verify only the matching row renders.

- [x] **Step 2: Review gates**

Run goal-review. Confirm no external data or private resume text is introduced.

- [ ] **Step 3: Commit, push, PR, merge**

Commit message:

```bash
git commit -m "Add saved jobs search and sort"
```

Push, create/open PR, merge after verification, then sync `main`.
