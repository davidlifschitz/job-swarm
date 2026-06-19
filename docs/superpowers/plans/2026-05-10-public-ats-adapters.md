# Public ATS Adapters Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add production Greenhouse and Lever public job-posting adapters and wire them into the web app by default.

**Architecture:** Create `ml_job_swarm/adapters.py` with GET-only adapter classes and a registry factory. Adapters accept an injectable fetcher for tests and return `RawJob` rows. `create_app()` uses `public_ats_registry()` as the default `adapter_registry`.

**Tech Stack:** Python stdlib `urllib.request`, `urllib.parse`, `json`, `html`, `re`; pytest.

---

## Files

- Create: `ml_job_swarm/adapters.py`
- Modify: `ml_job_swarm/app.py`
- Create: `tests/test_adapters_public_ats.py`
- Modify: `tests/test_routes_admin_sources.py`

## Task 1: Tests First

- [x] **Step 1: Add failing adapter tests**

Add tests that assert:

- Greenhouse board URLs map to the boards API and produce `RawJob`
- Lever URLs map to the postings API and produce `RawJob`
- bad URLs or bad payloads raise `RefreshError`

- [x] **Step 2: Add failing web default-registry test**

Add a route test that monkeypatches the public ATS HTTP fetcher, creates `create_app()`, posts `/admin/sources/refresh`, and proves jobs are inserted without manually overriding `app.state.adapter_registry`.

- [x] **Step 3: Verify red**

Run:

```bash
uv run pytest tests/test_adapters_public_ats.py tests/test_routes_admin_sources.py::test_admin_refresh_sources_uses_default_public_ats_registry -q
```

Expected: fail because adapters and default registry wiring do not exist.

## Task 2: Implementation

- [x] **Step 1: Create adapters module**

Implement `GreenhouseAdapter`, `LeverAdapter`, `_default_fetch_json`, `public_ats_registry`, and payload parsing helpers.

- [x] **Step 2: Wire app default registry**

Set `app.state.adapter_registry = public_ats_registry()` in `create_app`.

- [x] **Step 3: Verify focused and broad checks**

Run:

```bash
uv run pytest tests/test_adapters_public_ats.py tests/test_routes_admin_sources.py -q
uv run pytest -q
```

Expected: all tests pass.

## Task 3: Publish

- [x] **Step 1: Review gates**

Run goal-review. Confirm adapters are public GET-only, source-policy-gated by ingestion, and no auth/application/outreach behavior was introduced.

- [ ] **Step 2: Commit, push, PR, merge**

Commit message:

```bash
git commit -m "Add public ATS adapters"
```

Push, create/open PR, merge after verification, then sync `main`.
