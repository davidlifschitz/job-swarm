# Application Prep Workspace Plan

Spec: `docs/superpowers/specs/2026-05-10-application-prep-workspace-design.md`

## Goal

Add a local, prep-only application workspace for saved/job detail pages.

## Ownership

- Controller-owned files:
  - `ml_job_swarm/store.py`
  - `ml_job_swarm/app.py`
  - `ml_job_swarm/web/templates/job_detail.html`
  - `ml_job_swarm/web/templates/saved_jobs.html`
  - `tests/test_store_schema.py`
  - `tests/test_routes_onboarding.py`

## TDD Steps

1. Schema test: `application_packets` exists.
2. Job detail render test:
   - shows application workspace
   - has prepare form
   - does not show raw private resume text
3. Prepare route test:
   - creates one packet for job/profile
   - redirects to job detail
   - stored packet JSON includes local public job/fit data, not private text
4. Submitted status test:
   - marks packet `submitted`
   - redirects to job detail
5. Saved jobs page test:
   - shows prepare action for saved jobs.
6. Implement schema, helpers, routes, and templates.

## Verification

Focused:

```bash
uv run pytest tests/test_store_schema.py tests/test_routes_onboarding.py -q
```

Full:

```bash
uv run pytest
```

## Review Gates

- `goal-review`: confirm this advances real-world application workflow without autonomous submission.
- `test-quality-review`: confirm tests prove packet creation, status tracking, visibility, and privacy boundaries.
