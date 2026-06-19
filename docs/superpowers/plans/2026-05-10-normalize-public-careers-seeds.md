# Normalize Public Careers Seeds Implementation Plan

Spec: `docs/superpowers/specs/2026-05-10-normalize-public-careers-seeds-design.md`

## Goal

Route all reviewed seed primary sources through supported refresh adapters.

## Ownership

- Controller-owned files:
  - `data/seed_companies.json`
  - `tests/test_catalog.py`
  - this spec and plan pair

## TDD Steps

1. Add a catalog test that every seed primary `ats_type` exists in `public_ats_registry`.
2. Confirm the test fails on current `custom`/`unknown` seeds.
3. Convert unsupported public careers-page labels to `careers`.
4. Run catalog tests and full suite.

## Verification

```bash
uv run pytest tests/test_catalog.py -q
uv run pytest -q
```
