# Update Existing Seed Sources Implementation Plan

Spec: `docs/superpowers/specs/2026-05-10-update-existing-seed-sources-design.md`

## Goal

Ensure seed catalog corrections propagate into existing local SQLite databases.

## Ownership

- Controller-owned files:
  - `ml_job_swarm/catalog.py`
  - `tests/test_catalog.py`
  - this spec and plan pair

## TDD Steps

1. Add a regression test that imports stale seed metadata, re-imports corrected metadata, and asserts company/source fields update while imported count stays zero.
2. Confirm the regression fails before implementation.
3. Update `import_seed_companies` to upsert reviewed company metadata after `INSERT OR IGNORE`.
4. Update matching `job_sources` rows after `INSERT OR IGNORE`.
5. Run catalog tests and full suite.

## Verification

```bash
uv run pytest tests/test_catalog.py -q
uv run pytest -q
```
