# Seed Provider Link Backfill Implementation Plan

Spec: `docs/superpowers/specs/2026-05-10-seed-provider-link-backfill-design.md`

## Goal

Backfill verified direct provider sources discovered from existing public careers seed pages.

## Ownership

- Controller-owned files:
  - `data/seed_companies.json`
  - `tests/test_catalog.py`
  - this spec and plan pair

## TDD Steps

1. Add expected reviewed extra source assertions for newly discovered provider links.
2. Add a catalog guard that every extra source is allowed by source policy and matches `infer_source_type`.
3. Update `data/seed_companies.json` with verified direct provider sources.
4. Verify provider adapters return jobs for the added sources.
5. Run catalog tests and the full suite.

## Verification

```bash
uv run pytest tests/test_catalog.py -q
uv run pytest -q
```
