# Public Fetch Retry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Retry transient public fetch timeouts once before marking a public
source refresh failed.

**Architecture:** Add a small shared URL-open helper in `ml_job_swarm/adapters.py`
used by the default JSON, text, and POST JSON fetchers. Keep adapter parsing and
source-policy behavior unchanged.

**Tech Stack:** Python urllib, adapter unit tests with monkeypatched `urlopen`.

---

### Task 1: Failing Retry Tests

**Files:**
- Modify: `tests/test_adapters_public_ats.py`

- [ ] Add a JSON fetcher test where the first `urlopen` call raises
      `TimeoutError` and the second returns a valid response.
- [ ] Add a text fetcher test with the same timeout-then-success behavior.
- [ ] Add a POST JSON fetcher test with the same timeout-then-success behavior.
- [ ] Run the focused tests and confirm they fail before implementation.

### Task 2: Bounded Retry Helper

**Files:**
- Modify: `ml_job_swarm/adapters.py`

- [ ] Add a helper that opens urllib requests with one retry for transient
      timeout exceptions.
- [ ] Use the helper from `_default_fetch_json`, `_default_fetch_text`, and
      `_default_post_json`.
- [ ] Preserve existing `RefreshError(..., "blocked_response")` wrapping when
      retries are exhausted.
- [ ] Run focused tests until green.

### Task 3: Verification

**Files:**
- Review changed spec, plan, adapter tests, and fetch helper.

- [ ] Run goal-review.
- [ ] Run test-quality-review.
- [ ] Run `uv run pytest tests/test_adapters_public_ats.py -q`.
- [ ] Run `uv run pytest -q`.
- [ ] Push, open PR, wait for checks, merge, and sync main.
