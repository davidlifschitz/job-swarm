# Source Refresh Support Status Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show which admin source rows can be refreshed with the current adapter registry before the operator clicks refresh.

**Architecture:** Pass supported source types from app state into the source-health row builder, derive display-only row state there, and use the template to hide unsupported per-source refresh actions. Keep backend route guardrails unchanged.

**Tech Stack:** FastAPI, Jinja, pytest route tests.

---

### Task 1: Route Tests

**Files:**
- Modify: `tests/test_routes_admin_sources.py`

- [ ] Add a failing test that supported rows render `Ready` and a per-source refresh form.
- [ ] Add a failing test that unsupported enabled rows render `No adapter` and omit the per-source refresh form.
- [ ] Extend the disabled-source page test so disabled rows render `Disabled` and keep `Enable`.
- [ ] Run `uv run pytest tests/test_routes_admin_sources.py -q` and confirm the new assertions fail before implementation.

### Task 2: Source Row State

**Files:**
- Modify: `ml_job_swarm/app.py`
- Modify: `ml_job_swarm/web/templates/admin_sources.html`

- [ ] Pass `app.state.adapter_registry.source_types()` into `_source_health_rows`.
- [ ] Derive `adapter_status` and `adapter_status_label` for each source.
- [ ] Add a compact `Support` column.
- [ ] Render `Refresh` only when `adapter_status == "ready"`.
- [ ] Render `No adapter` for unsupported rows while preserving `Disable`.
- [ ] Run focused route tests until green.

### Task 3: Verification

**Files:**
- Review changed app, template, tests, spec, and plan.

- [ ] Run goal-review.
- [ ] Run test-quality-review.
- [ ] Browser-smoke seeded `/admin/sources` and verify unsupported rows are visible.
- [ ] Run `uv run pytest -q`.
- [ ] Push, open PR, wait for checks, merge, sync main.
