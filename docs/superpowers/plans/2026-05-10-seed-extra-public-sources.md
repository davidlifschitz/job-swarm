# Seed Extra Public Sources Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Import optional reviewed public ATS source rows from the seed catalog
without losing the canonical company careers URL.

**Architecture:** Extend seed parsing with a small `SeedSource` value object and
an `extra_sources` list on `SeedCompany`. Reuse the existing source-policy gate
and `job_sources` table; do not change ingestion contracts.

**Tech Stack:** JSON seed catalog, SQLite import, catalog tests.

---

### Task 1: Failing Catalog Tests

**Files:**
- Modify: `tests/test_catalog.py`

- [ ] Add a parser/import test for one company with one extra direct ATS source.
- [ ] Add a blocked extra-source regression.
- [ ] Add a default seed subset assertion for verified direct public ATS URLs.
- [ ] Run focused catalog tests and confirm the new tests fail before
      implementation/seed edits.

### Task 2: Parser and Import Support

**Files:**
- Modify: `ml_job_swarm/catalog.py`

- [ ] Add `SeedSource` and `SeedCompany.extra_sources`.
- [ ] Parse optional `extra_sources` entries with `url` and `source_type`.
- [ ] Policy-gate every source.
- [ ] Insert all sources idempotently for the imported company.
- [ ] Run focused tests until parser/import support is green.

### Task 3: Verified Seed Subset

**Files:**
- Modify: `data/seed_companies.json`

- [ ] Add direct public ATS `extra_sources` for OpenAI, Anthropic, Mistral AI,
      and CoreWeave.
- [ ] Keep normal company careers pages as `careers_url`.
- [ ] Run catalog tests until green.

### Task 4: Verification

**Files:**
- Review changed seed data, parser, tests, spec, and plan.

- [ ] Run goal-review.
- [ ] Run test-quality-review.
- [ ] Run `uv run pytest tests/test_catalog.py -q`.
- [ ] Run `uv run pytest -q`.
- [ ] Push, open PR, wait for checks, merge, and sync main.
