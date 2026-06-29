# Tier 2 — Hosted web (Railway + Supabase)

**Status: Phase B code complete** — Postgres schema, Storage backends, migration tooling, and cutover smoke ship on `main`. Production cutover requires `DATABASE_URL` + service role on Railway.

Public macOS installs remain Tier 1 ([tier1-macos-release.md](tier1-macos-release.md)). Tier 2 is the hosted FastAPI console and cloud runtime.

## Architecture

### Phase A (volume SQLite) — still supported

| Component | Role |
|-----------|------|
| **Railway** | Runs Dockerized FastAPI on `$PORT` |
| **Railway volume** | Persistent `/data` for SQLite + resume assets |
| **Supabase Auth** | Email/password login, JWT session (JWKS or legacy HS256) |
| **SQLite** | Default when `DATABASE_URL` is unset |

### Phase B (Supabase Postgres + Storage) — recommended for production

| Component | Role |
|-----------|------|
| **Supabase Postgres** | `DATABASE_URL` — global job catalog + per-user data with RLS |
| **Supabase Storage** | `resume-assets` bucket — private resume files per user |
| **Railway web** | FastAPI; no volume required for DB after cutover |
| **Railway worker** | `ML_JOB_SWARM_PROCESS=worker` drains `cloud_runs` queue |

When `DATABASE_URL` is set, `/healthz` reports `database_backend: postgresql`. When `SUPABASE_SERVICE_ROLE_KEY` (or `SUPABASE_SECRET_KEY`) and `SUPABASE_URL` are set, `resume_storage_backend: supabase`.

## Deploy checklist

### 1. Supabase

1. Create or link project (`supabase link --project-ref <ref>`).
2. Apply migrations: `supabase db push --linked`
3. Enable **Email** auth provider.
4. Copy from **Project Settings → API Keys**:
   - `SUPABASE_URL`
   - `SUPABASE_ANON_KEY` (publishable `sb_publishable_...`)
   - `SUPABASE_SERVICE_ROLE_KEY` (secret `sb_secret_...`, server-only)
5. **Database** → connection string (session pooler) → `DATABASE_URL`
6. **Storage** → create private bucket `resume-assets`; apply `supabase/storage/resume-assets-policies.sql`
7. JWT: new projects use JWKS via `SUPABASE_URL` — omit `SUPABASE_JWT_SECRET` unless legacy HS256.

Local secret sync:

```bash
./scripts/sync-supabase-secrets.sh          # writes .env.supabase.local
./scripts/sync-supabase-secrets.sh --railway # pushes anon key to Railway
```

### 2. Railway web

1. Deploy from GitHub → `davidlifschitz/job-swarm`.
2. **Phase A:** mount volume at `/data`.
3. **Phase B:** set Postgres + Storage env vars (volume optional after migration).

| Variable | Required | Notes |
|----------|----------|-------|
| `ML_JOB_SWARM_PUBLIC_URL` | Yes | e.g. `https://your-app.up.railway.app` |
| `SUPABASE_URL` | Yes | Auth |
| `SUPABASE_ANON_KEY` | Yes | Publishable key |
| `DATABASE_URL` | Phase B | Supabase pooler URI |
| `SUPABASE_SERVICE_ROLE_KEY` | Phase B | Resume Storage uploads |
| `ML_JOB_SWARM_RESUME_STORAGE_BUCKET` | Phase B | Default `resume-assets` |
| `ML_JOB_SWARM_DATA_DIR` | Phase A | `/data` when using SQLite |
| `OPENROUTER_API_KEY` | No | LLM fit review |

Verify:

```bash
curl -sS https://your-app.up.railway.app/healthz
./scripts/smoke-hosted.sh https://your-app.up.railway.app
./scripts/smoke-postgres-cutover.sh https://your-app.up.railway.app "$ACCESS_TOKEN"
```

### 3. Phase B cutover (SQLite → Postgres)

1. Export volume SQLite: `jobs.db` and `resume-assets/` (or use `railway ssh` when configured).
2. Dry-run migration:

```bash
export DATABASE_URL='postgresql://...'
ML_JOB_SWARM_SOURCE_DB=/path/to/jobs.db \
  ./scripts/railway-cutover.sh --dry-run
```

3. Live migration:

```bash
export DATABASE_URL='postgresql://...'
ML_JOB_SWARM_SOURCE_DB=/path/to/jobs.db \
ML_JOB_SWARM_RESUME_ASSET_DIR=/path/to/resume-assets \
  ./scripts/railway-cutover.sh
```

4. Redeploy web + worker with Phase B env vars on Railway.

5. Post-cutover smoke:

```bash
./scripts/railway-cutover.sh --smoke-only https://your-app.up.railway.app "$ACCESS_TOKEN"
```

### 4. Cloud worker

Second Railway service, same image:

| Variable | Value |
|----------|-------|
| `ML_JOB_SWARM_PROCESS` | `worker` |
| `DATABASE_URL` | Same as web (Phase B) |
| `SUPABASE_*` | Same as web if worker touches Storage |

Phase A: mount **same volume** at `/data`. Phase B: Postgres queue only — shared volume not required.

`scripts/start-cloud-worker.sh` runs `ml-job-swarm-cloud-worker --max-runs 0` (daemon). Worker uses `connect_from_env()` when `DATABASE_URL` is set.

### 5. Per-user isolation

Scoped by Supabase JWT `sub`: `target_profiles`, `linkedin_connections`, `resume_assets`, `cloud_runs`. Legacy `user_id = ''` rows are invisible after sign-in — re-upload resume and re-import `Connections.csv`.

### 6. Pre-deploy smoke (local)

```bash
./scripts/railway-preflight.sh              # Phase A SQLite container
PREFLIGHT_POSTGRES=1 ./scripts/railway-preflight.sh  # + Phase B Postgres smoke
```

## Local development

Auth disabled when Supabase env vars are unset:

```bash
uv sync
ML_JOB_SWARM_DB_PATH=jobs.db uv run uvicorn 'ml_job_swarm.app:create_app_from_env' --factory --host 127.0.0.1 --port 8765
```

Postgres locally:

```bash
export DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:5432/jobs
export ML_JOB_SWARM_TEST_DATABASE_URL="${DATABASE_URL}"
uv run pytest tests/test_postgres_schema.py -q
```

## CI

`.github/workflows/ci.yml` runs `postgres-tests` with a `postgres:16` service and all `test_*_postgres.py` / hosted migration tests.

## Related docs

- [cloud-production-server-goals.md](cloud-production-server-goals.md) — cloud runtime SLOs (post-Phase B)
- [product-tiers.md](product-tiers.md) — tier overview

## Dry-run verification checklist (local, no production secrets)

Run these before Railway/Supabase cutover. They use Docker sidecars, fixture adapters, and test JWTs — no live `DATABASE_URL`, service-role keys, or Railway tokens required.

### 1. Full test suite

```bash
uv sync
uv run pytest -q
```

Expect ~530 passed, 12 skipped.

### 2. Hosted container preflight (Phase A SQLite)

```bash
./scripts/railway-preflight.sh
```

Builds the Docker image, starts a container with fake Supabase env vars, hits `/healthz`, and runs `scripts/smoke-hosted.sh` (auth gate + signed JWT path).

### 3. Phase B Postgres preflight (optional)

```bash
PREFLIGHT_POSTGRES=1 ./scripts/railway-preflight.sh
```

Adds a local `postgres:16-alpine` sidecar and verifies `database_backend: postgresql` plus Supabase Storage mode via `scripts/smoke-postgres-cutover.sh`.

### 4. Env template sanity

```bash
grep -E '^[A-Z_]+=' .env.hosted.example | cut -d= -f1 | sort
```

Confirm vars match the tables in this doc (web + worker + Phase A/B blocks).

### 5. Offline seed refresh audit

```bash
db="$(mktemp /tmp/seed-audit-XXXXXX.db)"
uv run python scripts/seed_refresh_audit.py --db "${db}"
rm -f "${db}"
```

Expect JSON with `audit_passed: true`, attempted/succeeded counts, and no fixture refresh failures.

### 6. Product gate subset (matches CI `product-gates` job)

```bash
uv run pytest -q \
  tests/test_product_goals.py \
  tests/test_seed_policy_gate.py \
  tests/test_seed_refresh_audit.py \
  tests/test_golden_profile_matching.py \
  tests/test_catalog_quality_gate.py \
  tests/test_error_handling_gates.py \
  tests/test_operator_observability_gate.py
```

### 7. Cloud runtime parity fixtures

```bash
chmod +x scripts/run-cloud-parity-check.sh
./scripts/run-cloud-parity-check.sh
```

### 8. Cloud health probe (against preflight container)

After step 2 leaves a healthy container (or start the app locally on port 8765):

```bash
BASE_URL=http://127.0.0.1:18080 ./scripts/cloud-health-probe.sh
# or: BASE_URL=http://127.0.0.1:8765 ./scripts/cloud-health-probe.sh
```

### 9. SQLite → Postgres migration dry-run (local Postgres only)

With a local Postgres instance (no Supabase secrets):

```bash
export DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:5432/jobs
ML_JOB_SWARM_DB_PATH=/tmp/ml-job-swarm-migrate.db uv run pytest tests/test_hosted_migration.py -q
export ML_JOB_SWARM_SOURCE_DB=/tmp/ml-job-swarm-migrate.db
./scripts/railway-cutover.sh --dry-run
```

### Ops-only (requires production secrets — not dry-run)

These steps cannot be verified locally without maintainer credentials:

- **OPS-1** Railway Phase B cutover: set live `DATABASE_URL`, run `railway-cutover.sh` (non–dry-run), deploy worker service.
- **OPS-2** Supabase bucket creation + secret rotation: `supabase link`, `supabase db push`, Storage policies, `./scripts/sync-supabase-secrets.sh --railway`.
- **OPS-3** Apple notarization / Tier 3 release (see `docs/tier1-macos-release.md`).
- **Nightly live seed audit**: scheduled `.github/workflows/nightly-seed-audit.yml` (W4-T2) — pending; offline audit in step 5 is the local substitute.