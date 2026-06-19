# Tier 2 — Hosted web (Railway + Supabase)

**Status: Phase A in progress** — Railway deploy artifacts and Supabase Auth gate.

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
3. Copy from **Project Settings → API**:
   - `SUPABASE_URL`
   - `SUPABASE_ANON_KEY`
4. Copy **JWT Secret** from **Project Settings → API → JWT Settings**:
   - `SUPABASE_JWT_SECRET`

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
| `SUPABASE_JWT_SECRET` | `your-jwt-secret` | Yes |
| `OPENROUTER_API_KEY` | `sk-or-...` | No |
| `ML_JOB_SWARM_SEED_COMPANIES` | `data/seed_companies.json` | No |

4. Deploy. Railway sets `PORT` automatically.
5. Verify:
   - `GET /healthz` → `200` (no auth)
   - `GET /dashboard` → redirects to `/auth/login`
   - Sign in → dashboard loads

### 3. Optional cloud worker

Add a second Railway service (same repo/image) with start command:

```bash
uv run ml-job-swarm-cloud-worker --max-runs 0
```

Use `--max-runs 0` for a long-running drain loop, or invoke `POST /api/cloud/worker/run-next` from a cron.

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