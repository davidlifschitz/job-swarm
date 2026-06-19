# Ignore Generic Provider Links Implementation Plan

Spec: `docs/superpowers/specs/2026-05-10-ignore-generic-provider-links-design.md`

## Goal

Prevent static careers-page discovery from delegating known generic provider links as job boards.

## Ownership

- Controller-owned files:
  - `ml_job_swarm/adapters.py`
  - `tests/test_adapters_public_ats.py`
  - this spec and plan pair

## TDD Steps

1. Add a regression test for `https://boards.greenhouse.io/job-boards` proving no provider adapter call occurs.
2. Confirm the regression fails before implementation.
3. Add a minimal denylist for generic Greenhouse board tokens.
4. Verify real Greenhouse board delegation remains green.
5. Run focused adapter tests and full suite.

## Verification

```bash
uv run pytest tests/test_adapters_public_ats.py -q
uv run pytest -q
```
