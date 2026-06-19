# Careers JSON-LD Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a safe public employer-page adapter that ingests Schema.org `JobPosting` JSON-LD from user-submitted careers pages.

**Architecture:** Add `CareersJsonLdAdapter` to `ml_job_swarm/adapters.py`, backed by a text fetcher and a narrow JSON-LD parser. Register it as source type `careers` so source-review approval can refresh user-submitted generic careers pages that expose structured job postings.

**Tech Stack:** Python stdlib HTML/JSON parsing, existing ingestion adapter protocol, pytest unit and route tests.

---

### Task 1: Adapter Contract

**Files:**
- Modify: `tests/test_adapters_public_ats.py`
- Modify: `ml_job_swarm/adapters.py`

- [x] **Step 1: Write failing adapter tests**

Cover a single `JobPosting`, `@graph` payloads, pages without job postings, and
unsupported non-careers URLs.

- [x] **Step 2: Implement adapter**

Fetch public HTML, extract `application/ld+json` scripts, collect nodes typed
as `JobPosting`, and map safe public fields into `RawJob`.

- [x] **Step 3: Register source type**

Add `careers` to `public_ats_registry()` so reviewed source refresh and
approve-and-refresh can use it.

### Task 2: Web Integration

**Files:**
- Modify: `tests/test_routes_admin_sources.py`

- [x] **Step 1: Write route integration test**

Submit a generic careers page, approve-and-refresh it with a fake JSON-LD page,
and assert the job row is inserted.

- [x] **Step 2: Verify focused tests**

Run:

```bash
uv run pytest tests/test_adapters_public_ats.py tests/test_routes_admin_sources.py tests/test_ingest.py -q
```

### Task 3: Review And Publish

- [x] **Step 1: Run review gates**

Use goal-review and test-quality-review against the final diff.

- [x] **Step 2: Verify**

Run:

```bash
uv run pytest -q
```

- [x] **Step 3: Push PR**

Use github-push to commit, push, open the PR, and merge when checks allow.
