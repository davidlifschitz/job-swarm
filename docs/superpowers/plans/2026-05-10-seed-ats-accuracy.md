# Seed ATS Accuracy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop known generic careers pages from being routed through specific
ATS adapters after live refresh evidence shows they fail there.

**Architecture:** Keep adapter behavior unchanged for this narrow slice. Patch
seed metadata for evidence-backed failures and lock the regression in catalog
tests. A later source-verification slice can discover direct ATS board URLs or
broaden adapter URL contracts with live evidence.

Live smoke found one narrow adapter contract gap: `.careers` domains should be
accepted by the generic careers adapter because they are public careers pages,
not specific ATS boards.

**Tech Stack:** JSON seed catalog, Python catalog tests, FastAPI admin smoke.

---

### Task 1: Failing Seed Regression

**Files:**
- Modify: `tests/test_catalog.py`

- [ ] Add a test listing the live-failing companies and asserting their
      `ats_type` is not `greenhouse` or `ashby`.
- [ ] Run focused catalog tests and confirm the new regression fails.

### Task 2: Seed Corrections

**Files:**
- Modify: `data/seed_companies.json`

- [ ] Change the 15 evidence-backed generic careers URLs from `greenhouse` or
      `ashby` to `careers`.
- [ ] Keep URLs unchanged unless a direct public ATS board URL is verified.
- [ ] Run focused catalog tests until green.

### Task 3: Verification

**Files:**
- Review changed seed data, tests, spec, and plan.

- [ ] Run goal-review.
- [ ] Run test-quality-review.
- [ ] Run `uv run pytest tests/test_catalog.py -q`.
- [ ] Run `uv run pytest tests/test_adapters_public_ats.py -q`.
- [ ] Run `uv run pytest -q`.
- [ ] Run a local seeded admin refresh smoke if it can complete without
      credentials or restricted sources.
- [ ] Push, open PR, wait for checks, merge, and sync main.
