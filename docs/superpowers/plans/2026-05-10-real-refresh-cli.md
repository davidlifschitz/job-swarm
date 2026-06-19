# Real Public Refresh CLI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Add an explicit real public ATS mode to the cron-friendly refresh CLI.

**Architecture:** Keep fixture mode as the deterministic adapter path, and add a
second registry source using `public_ats_registry()`. The refresh orchestration
continues to call `refresh_due_sources(conn, registry, source_types=registry.source_types())`.

**Tech Stack:** Python argparse, SQLite, existing `AdapterRegistry`, pytest.

---

### Task 1: Public Registry Mode

**Files:**
- Modify: `tests/test_cli.py`
- Modify: `ml_job_swarm/cli.py`

- [x] **Step 1: Write the failing public-mode test**

Add a test that monkeypatches `ml_job_swarm.cli.public_ats_registry` to return
an in-memory `AdapterRegistry` with fixture `RawJob` rows. Seed one supported
source and one unsupported source. Assert the JSON summary reports one
refreshed source, one skipped source, and one inserted job.

- [x] **Step 2: Run the test to verify it fails**

Run:

```bash
uv run pytest tests/test_cli.py::test_refresh_command_can_use_public_ats_registry -q
```

Expected: fails because `--public-ats` is not recognized.

- [x] **Step 3: Implement `--public-ats`**

In `ml_job_swarm/cli.py`, import `public_ats_registry`, add a boolean
`--public-ats` argument, make `--fixture-dir` optional, and select the registry:

```python
registry = public_ats_registry() if args.public_ats else _fixture_registry(Path(args.fixture_dir))
```

- [x] **Step 4: Run focused CLI tests**

Run:

```bash
uv run pytest tests/test_cli.py -q
```

Expected: all CLI tests pass.

### Task 2: Adapter Mode Validation And Docs

**Files:**
- Modify: `tests/test_cli.py`
- Modify: `ml_job_swarm/cli.py`
- Modify: `README.md`

- [x] **Step 1: Write the failing validation test**

Add a test that calls `main(["refresh", "--db", str(db_path)])` and expects an
argparse `SystemExit` plus an error mentioning `--public-ats` and
`--fixture-dir`.

- [x] **Step 2: Add validation**

In `main`, use `refresh.add_mutually_exclusive_group(required=True)` for
`--public-ats` and `--fixture-dir`. This keeps accidental live/fixture ambiguity
out of the runtime path and lets argparse produce a clear error.

- [x] **Step 3: Update README**

Document real daily refresh:

```bash
uv run ml-job-swarm refresh --public-ats --db jobs.db --seed data/seed_companies.json
```

Keep fixture refresh as a test/development command.

- [x] **Step 4: Verify**

Run:

```bash
uv run pytest tests/test_cli.py -q
uv run pytest
```

Expected: full suite passes.

## Review Gates

- `goal-review`: confirm this turns the scheduled path into real public-source
  work without adding prohibited scraping or application actions.
- `test-quality-review`: confirm tests prove public registry selection, fixture
  compatibility, mode validation, skipped source accounting, and no live network
  calls in tests.
