# Greenhouse Host Fallback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add tested host-derived Greenhouse board fallback for reviewed company careers pages.

**Architecture:** Extend only Greenhouse board-token extraction in `ml_job_swarm/adapters.py`. Keep the adapter fetch path unchanged so all successful fallback requests still use the existing public Greenhouse GET API and all wrong guesses fail through existing refresh friction.

**Tech Stack:** Python URL parsing, existing public ATS adapter tests, pytest.

---

### Task 1: Host-Derived Greenhouse Tokens

**Files:**
- Modify: `tests/test_adapters_public_ats.py`
- Modify: `ml_job_swarm/adapters.py`

- [x] **Step 1: Write failing host-fallback tests**

Add tests for:

- `https://www.anthropic.com/careers` -> `anthropic`
- `https://careers.airbnb.com/` -> `airbnb`
- `https://about.gitlab.com/jobs/` -> `gitlab`
- `https://x.ai/careers` -> `xai`

Each test should inject a fake fetcher and assert the exact Greenhouse API URL.

- [x] **Step 2: Write failing non-careers rejection test**

Add a test with `https://example.com/about` and a fetcher that would fail if
called. Assert `GreenhouseAdapter.fetch_jobs()` raises `RefreshError`.

- [x] **Step 3: Implement fallback**

Update `_greenhouse_board_token()` to keep exact Greenhouse handling first, then
derive a host token only when the path contains a careers/jobs marker. Strip
common display prefixes and join short two-label hosts such as `x.ai`.

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

- [x] **Step 2: Run public seed smoke**

Run a temp DB refresh:

```bash
uv run ml-job-swarm refresh --public-ats --db <tmp>/jobs.db --seed data/seed_companies.json
```

Expected: the command may still exit nonzero because unrelated source drift
remains, but Greenhouse `Unsupported Greenhouse source URL` friction should be
reduced.

## Review Gates

- `goal-review`: confirm the fallback increases real public refresh coverage
  without adding prohibited scraping.
- `test-quality-review`: confirm tests prove token inference, direct behavior,
  rejection behavior, and no live network in unit tests.
