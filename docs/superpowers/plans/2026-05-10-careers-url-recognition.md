# Careers URL Recognition Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Broaden safe careers-page recognition for the JSON-LD adapter without allowing arbitrary page fetches.

**Architecture:** Extend the existing `_looks_like_careers_page` predicate with additional public careers URL shapes observed in the seed catalog probe.

---

### Task 1: Tests First

**Files:**
- Modify: `tests/test_adapters_public_ats.py`

- [x] **Step 1: Add failing URL-shape tests**

Assert the `careers` adapter accepts `.jobs`, `/open-positions/`, and
`/career-opportunities/` URLs when the page has JSON-LD.

### Task 2: Implementation

**Files:**
- Modify: `ml_job_swarm/adapters.py`

- [x] **Step 1: Extend recognition**

Add `.jobs` hosts and the two path markers while keeping generic `/about`
blocked before fetch.

### Task 3: Review And Publish

- [x] **Step 1: Run review gates**

Confirm the change only broadens public careers-page recognition and does not
add crawling, auth, cookies, CAPTCHA bypass, or aggregator scraping.

- [x] **Step 2: Verify**

Run:

```bash
uv run pytest tests/test_adapters_public_ats.py -q
uv run pytest -q
```

- [x] **Step 3: Push PR**

Use github-push to commit, push, open the PR, and merge when checks allow.
