# Lever Host Fallback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a tested host-derived Lever site fallback for reviewed company careers pages.

**Architecture:** Reuse the same careers-page and host-token helpers already used by Greenhouse. Extend only `_lever_site()` so direct Lever URLs remain first and fallback requests still use the existing public Lever GET endpoint.

**Tech Stack:** Python URL parsing, existing public ATS adapter tests, pytest.

---

### Task 1: Host-Derived Lever Site Slugs

**Files:**
- Modify: `tests/test_adapters_public_ats.py`
- Modify: `ml_job_swarm/adapters.py`

- [x] **Step 1: Write failing host-fallback tests**

Add tests for `https://mistral.ai/careers` -> `mistral` and
`https://careers.example.com/` -> `example`, asserting exact Lever API URLs.

- [x] **Step 2: Write failing non-careers rejection test**

Add a test with `https://example.com/about` and a fetcher that fails if called.
Assert `LeverAdapter.fetch_jobs()` raises `RefreshError`.

- [x] **Step 3: Implement fallback**

Update `_lever_site()` to keep exact Lever handling first, then derive a host
slug only when `_looks_like_careers_page(host, segments)` returns true.

- [x] **Step 4: Verify focused tests**

Run:

```bash
uv run pytest tests/test_adapters_public_ats.py -q
```

Expected: public ATS adapter tests pass.

### Task 2: Regression And Runtime Smoke

**Files:**
- No extra files unless review finds a gap.

- [x] **Step 1: Run broader tests**

Run:

```bash
uv run pytest tests/test_adapters_public_ats.py tests/test_ingest.py tests/test_cli.py -q
uv run pytest
```

Expected: full suite passes.

- [x] **Step 2: Run Mistral public refresh smoke**

Run a temp DB refresh with a one-company Mistral seed:

```bash
uv run ml-job-swarm refresh --public-ats --db <tmp>/jobs.db --seed <mistral-seed.json>
```

Expected: command exits 0 and inserts jobs from the public Lever feed.

## Review Gates

- `goal-review`: confirm the fallback increases real public refresh coverage
  without adding prohibited scraping.
- `test-quality-review`: confirm tests prove Lever slug inference, direct
  behavior, rejection behavior, and no live network in unit tests.
