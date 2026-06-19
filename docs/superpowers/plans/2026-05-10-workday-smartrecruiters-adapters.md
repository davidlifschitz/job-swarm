# Workday And SmartRecruiters Public Adapters Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add safe public Workday and SmartRecruiters adapter coverage to the website refresh pipeline.

**Architecture:** Extend `ml_job_swarm/adapters.py` with two adapter classes that follow existing `RawJob` and `RefreshError` contracts. Keep URL support strict so generic employer pages are not fetched with the wrong adapter. Correct seed metadata so default web refresh does not create avoidable friction.

**Tech Stack:** Python stdlib HTTP, SQLite-backed ingestion, pytest.

---

### Task 1: Adapter Tests

**Files:**
- Modify: `tests/test_adapters_public_ats.py`

- [ ] Add Workday tests for direct board URL parsing, locale URL parsing, exact CXS POST request body with `limit=20`, pagination, raw job mapping, malformed payload, and unsupported URL rejection.
- [ ] Add SmartRecruiters tests for board/API URL parsing, exact list/detail requests, pagination, raw job mapping, malformed payload, and unsupported URL rejection.
- [ ] Add a registry test requiring `greenhouse`, `lever`, `ashby`, `careers`, `workday`, and `smartrecruiters`.
- [ ] Add a seed metadata test requiring `workday` URLs to end in `myworkdayjobs.com` and `smartrecruiters` URLs to end in `smartrecruiters.com`.
- [ ] Run `uv run pytest tests/test_adapters_public_ats.py -q` and confirm the new tests fail before implementation.

### Task 2: Public Adapters

**Files:**
- Modify: `ml_job_swarm/adapters.py`

- [ ] Add `JsonPostFetcher` and `_default_post_json`.
- [ ] Add `WorkdayAdapter` with strict URL parsing, public CXS POST pagination, and `RawJob` mapping.
- [ ] Add `SmartRecruitersAdapter` with strict URL parsing, public Posting API pagination, detail fetches, and `RawJob` mapping.
- [ ] Register both adapters in `public_ats_registry()`.
- [ ] Run focused adapter tests until green.

### Task 3: Seed Corrections

**Files:**
- Modify: `data/seed_companies.json`

- [ ] Change NVIDIA to a direct public Workday URL.
- [ ] Change Snowflake to `careers`.
- [ ] Change Block to `careers`.
- [ ] Run focused adapter tests again so seed metadata stays valid.

### Task 4: Verification

**Files:**
- Review changed code, tests, specs, and seed data.

- [ ] Run goal-review against the implementation.
- [ ] Run test-quality-review against the tests.
- [ ] Run `uv run pytest tests/test_adapters_public_ats.py -q`.
- [ ] Run `uv run pytest -q`.
- [ ] Push the branch, open the PR, wait for checks, merge, and sync `main`.
