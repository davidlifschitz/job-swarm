# Runtime Seeded App Design

Branch: `codex/runtime-seeded-app`

## Goal

Make the deployed/local website start with a persistent database and reviewed company source catalog, instead of requiring manual seed commands before the UI can do useful work.

## Problem

`create_app()` is intentionally good for tests, but its default in-memory DB means a normal web launch has no durable state and no seed companies. The CLI can import `data/seed_companies.json`, but the website runtime does not do that automatically.

## V1 Scope

- Add a runtime app factory separate from `create_app()`.
- Read:
  - `ML_JOB_SWARM_DB_PATH`, default `jobs.db`
  - `ML_JOB_SWARM_SEED_COMPANIES`, default `data/seed_companies.json`
- Import seed companies idempotently when the seed file exists.
- Keep `create_app()` unchanged for tests and in-memory workflows.
- Update README local-run command to use the runtime factory.

## Safety Boundary

- Importing the seed catalog creates local company/source rows only.
- It does not fetch jobs, scrape websites, call LLMs, open browsers, or submit applications.
- Existing source policy still validates seed URLs before import.

## Acceptance Criteria

- Runtime factory creates a persistent DB at the configured path.
- Runtime factory imports configured seed companies exactly once across repeated starts.
- Admin sources page shows seeded reviewed sources.
- Full tests pass.

## Later Scope

- Cloudflare cron setup.
- Admin-authenticated hosted deployment.
- Seed catalog update management UI.
