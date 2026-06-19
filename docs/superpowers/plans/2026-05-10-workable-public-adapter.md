# Workable Public Adapter Implementation Plan

Spec: `docs/superpowers/specs/2026-05-10-workable-public-adapter-design.md`

## Goal

Make reviewed Workable public sources refreshable through the same public ATS path as Greenhouse, Lever, Ashby, Workday, and SmartRecruiters.

## Ownership

- Controller-owned files:
  - `ml_job_swarm/adapters.py`
  - `tests/test_adapters_public_ats.py`
  - this spec and plan pair

## TDD Steps

1. Add failing adapter tests.
   - Fetches public Workable account jobs from `apply.workable.com/{subdomain}`.
   - Accepts API source URL shape.
   - Rejects unsupported Workable job-shortcode URL before fetch.
   - Rejects malformed payload.
   - Registry includes `workable`.
2. Implement `WorkableAdapter`.
   - Derive account subdomain from supported URL shapes.
   - Fetch public jobs with `details=true`.
   - Parse job fields into `RawJob`.
3. Register `workable` in `public_ats_registry()`.
4. Run focused adapter tests and full suite.

## Acceptance Checks

- Refreshing a reviewed Workable source can produce normalized jobs.
- No private credentials or authenticated Workable endpoints are used.
- Existing source-policy restrictions remain unchanged.

## Verification

```bash
uv run pytest tests/test_adapters_public_ats.py -q
uv run pytest -q
```
