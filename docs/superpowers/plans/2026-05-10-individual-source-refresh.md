# Individual Source Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a website action that refreshes one reviewed source through the real ingestion pipeline.

**Architecture:** Reuse the existing `refresh_source` and run-summary redirect plumbing. Keep route-level guardrails in `ml_job_swarm/app.py` so unsupported, missing, or disabled sources do not run adapters. Extend the existing admin source route tests before touching production code.

**Tech Stack:** FastAPI, Jinja templates, SQLite, pytest, `TestClient`.

---

### Task 1: Route Tests

**Files:**
- Modify: `tests/test_routes_admin_sources.py`

- [ ] Add a failing test that `/admin/sources` renders `action="/admin/sources/{source_id}/refresh"` for an enabled source.
- [ ] Add a failing test that `POST /admin/sources/{source_id}/refresh` with a supported adapter inserts one job, marks the source checked, and redirects to `/admin/runs?refresh_status=completed&sources_seen=1&sources_refreshed=1&sources_skipped=0&jobs_seen=1&failures=0&blocked=0`.
- [ ] Add a failing test that an unsupported source type redirects with `sources_skipped=1`, adapter calls stay zero, no ingestion run is created, and no friction event is created.
- [ ] Add failing tests that disabled and missing source IDs return errors without calling adapters.
- [ ] Run `uv run pytest tests/test_routes_admin_sources.py -q` and verify the new tests fail for missing behavior.

### Task 2: Route And Template

**Files:**
- Modify: `ml_job_swarm/app.py`
- Modify: `ml_job_swarm/web/templates/admin_sources.html`

- [ ] Add `POST /admin/sources/{source_id}/refresh`.
- [ ] Load `source_type` and `disabled_at` for the source.
- [ ] Return `404` when the source does not exist.
- [ ] Return `400` when disabled.
- [ ] Redirect with `sources_skipped=1` for unsupported source types.
- [ ] Call `refresh_source` for supported sources and redirect with one-source summary counts.
- [ ] Add the `Refresh` form next to the company name in enabled source rows.
- [ ] Run `uv run pytest tests/test_routes_admin_sources.py -q` and verify the route tests pass.

### Task 3: Review And Verification

**Files:**
- Review: `docs/superpowers/specs/2026-05-10-individual-source-refresh-design.md`
- Review: `docs/superpowers/plans/2026-05-10-individual-source-refresh.md`
- Review: changed app, template, and tests

- [ ] Run goal-review against the slice.
- [ ] Run test-quality-review against the tests.
- [ ] Run `uv run pytest -q`.
- [ ] Browser-smoke `/admin/sources` and verify each enabled source row exposes `Refresh now` without layout overflow.
- [ ] Push the branch and create a PR.
