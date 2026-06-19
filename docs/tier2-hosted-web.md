# Tier 2 — Hosted web (Railway + Supabase)

**Status: Phase A complete** — Railway deploy, Supabase Auth, volume-backed SQLite, per-user data isolation, and optional cloud worker.

Public macOS installs remain Tier 1 ([tier1-macos-release.md](tier1-macos-release.md)). Tier 2 is the hosted FastAPI console and cloud runtime.

## Architecture (Phase A)

| Component | Role |
|-----------|------|
| **Railway** | Runs Dockerized FastAPI on `$PORT` |
| **Railway volume** | Persistent `/data` for SQLite + resume assets |
| **Supabase Auth** | Email/password login, JWT session |
| **SQLite** | Same schema as local dev (Postgres in Phase B) |

## Deploy checklist

### 1. Supabase

1. Create a project at [supabase.com](https://supabase.com).
2. Enable **Email** provider (password sign-in).
3. Copy from **Project Settings → API Keys**:
   - `SUPABASE_URL` (project URL)
   - `SUPABASE_ANON_KEY` — the **publishable** key (`sb_publishable_...`), not the secret key
4. JWT verification:
   - **New projects (JWT signing keys / ES256):** leave `SUPABASE_JWT_SECRET` unset; the app verifies tokens via JWKS
   - **Legacy projects (HS256):** set `SUPABASE_JWT_SECRET` from **JWT Settings**

### 2. Railway

1. New project → **Deploy from GitHub** → `davidlifschitz/job-swarm`.
2. Add a **volume** mounted at `/data`.
3. Set environment variables:

| Variable | Example | Required |
|----------|---------|----------|
| `ML_JOB_SWARM_DATA_DIR` | `/data` | Yes |
| `ML_JOB_SWARM_PUBLIC_URL` | `https://your-app.up.railway.app` | Yes |
| `SUPABASE_URL` | `https://xyz.supabase.co` | Yes |
| `SUPABASE_ANON_KEY` | `eyJ...` | Yes |
| `SUPABASE_JWT_SECRET` | `your-jwt-secret` | Legacy HS256 only |
| `OPENROUTER_API_KEY` | `sk-or-...` | No |
| `ML_JOB_SWARM_SEED_COMPANIES` | `data/seed_companies.json` | No |

4. Deploy. Railway sets `PORT` automatically.
5. Verify:
   - `GET /healthz` → `200` (no auth)
   - `GET /dashboard` → redirects to `/auth/login`
   - Sign in → dashboard loads

### 3. Cloud worker (recommended)

Add a second Railway service from the same repo/image:

1. Mount the **same volume** at `/data` (shared SQLite queue).
2. Set the same env vars as the web service (`ML_JOB_SWARM_DATA_DIR`, Supabase keys if needed).
3. Override the start command:

```bash
./scripts/start-cloud-worker.sh
```

`--max-runs 0` drains queued cloud runs in a loop (daemon mode). Alternatively, invoke `POST /api/cloud/worker/run-next` from a cron on the web service.

### 4. Per-user isolation

Hosted mode scopes these records by Supabase JWT `sub`:

- `target_profiles`
- `linkedin_connections` / imports
- `resume_assets`
- `cloud_runs`

Legacy rows imported before auth scoping have `user_id = ''` and are not visible to signed-in users — re-upload resumes and re-import `Connections.csv` after signing in.

### 5. Pre-deploy smoke (local)

```bash
./scripts/railway-preflight.sh
```

Builds the Docker image, starts a container with a temp `/data` volume, and runs `smoke-hosted.sh` against `http://127.0.0.1:18080`.

### 6. Post-deploy smoke

```bash
./scripts/smoke-hosted.sh https://your-app.up.railway.app
# With a Supabase access token:
./scripts/smoke-hosted.sh https://your-app.up.railway.app "$ACCESS_TOKEN"
```

## Local development

Auth is **disabled** when Supabase env vars are unset. Run as before:

```bash
uv sync
ML_JOB_SWARM_DB_PATH=jobs.db \
ML_JOB_SWARM_SEED_COMPANIES=data/seed_companies.json \
uv run uvicorn 'ml_job_swarm.app:create_app_from_env' --factory --host 127.0.0.1 --port 8765
```

To test auth locally:

```bash
export SUPABASE_URL=https://your-project.supabase.co
export SUPABASE_ANON_KEY=...
export SUPABASE_JWT_SECRET=...
uv run uvicorn 'ml_job_swarm.app:create_app_from_env' --factory --host 127.0.0.1 --port 8765
```

## Phase B (later)

- Migrate SQLite → **Supabase Postgres** (`DATABASE_URL`)
- Resume assets → **Supabase Storage**
- See [cloud-production-server-goals.md](cloud-production-server-goals.md) for production SLOs