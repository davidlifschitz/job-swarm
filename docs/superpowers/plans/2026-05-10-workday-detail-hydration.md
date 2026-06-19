# Workday Detail Hydration Implementation Plan

Spec: `docs/superpowers/specs/2026-05-10-workday-detail-hydration-design.md`

## Goal

Use public Workday detail JSON to improve normalized job descriptions and requirements.

## Ownership

- Controller-owned files:
  - `ml_job_swarm/adapters.py`
  - `tests/test_adapters_public_ats.py`
  - this spec and plan pair

## TDD Steps

1. Add Workday adapter tests:
   - list posting detail URL is fetched and merged into `RawJob`
   - detail fetch failure returns list-derived job
2. Add optional `fetch_json` dependency to `WorkdayAdapter`.
3. Derive detail URL from host, tenant, site, and `externalPath`.
4. Merge detail fields conservatively.
5. Run focused adapter tests and full suite.

## Verification

```bash
uv run pytest tests/test_adapters_public_ats.py -q
uv run pytest -q
```
