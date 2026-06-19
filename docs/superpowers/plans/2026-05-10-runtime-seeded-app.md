# Runtime Seeded App Plan

Spec: `docs/superpowers/specs/2026-05-10-runtime-seeded-app-design.md`

## Goal

Add an env-driven runtime app factory that persists `jobs.db` and idempotently imports the reviewed seed catalog.

## Ownership

- Controller-owned files:
  - `ml_job_swarm/app.py`
  - `README.md`
  - `tests/test_routes_admin_sources.py`

## TDD Steps

1. Add a route/runtime test that sets temp env vars and calls `create_app_from_env()`.
2. Assert companies/job_sources are seeded and admin sources renders them.
3. Call the factory twice against the same DB and assert no duplicate sources.
4. Implement env factory and seed import helper.
5. Update README run command.

## Verification

Focused:

```bash
uv run pytest tests/test_routes_admin_sources.py -q
```

Full:

```bash
uv run pytest
```

## Review Gates

- `goal-review`: confirm this makes the website runtime useful without triggering live external actions.
- `test-quality-review`: confirm tests prove persistence, idempotent seeding, and admin visibility.
