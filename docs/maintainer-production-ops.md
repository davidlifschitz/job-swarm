# Maintainer production OPS runbook

**Audience:** ml-job-swarm maintainers with production credentials.

**Scope:** OPS-2 (Supabase), OPS-1 (Railway Phase B cutover), OPS-3 (Apple notarization). These steps require live secrets and cannot be fully automated in CI.

**Related docs:**

- [Tier 2 — Hosted web (Railway + Supabase)](tier2-hosted-web.md) — architecture, Phase A/B env catalog, cutover detail
- [Tier 3 — App stores](tier3-app-stores.md) — notarized macOS distribution goals and Apple Developer setup

---

## Overview

| OPS | Name | Scripts | When |
|-----|------|---------|------|
| **OPS-2** | Supabase hygiene | `bootstrap-supabase.sh`, `sync-supabase-secrets.sh --railway` | First — Postgres schema, API keys, Railway secret sync |
| **OPS-1** | Railway Phase B cutover | `railway-cutover.sh` | Second — migrate hosted SQLite → Postgres, smoke live app |
| **OPS-3** | Apple notarization | `notarize-macos-app.sh --require` | Third — macOS release (requires macOS + Developer creds) |

**Recommended order:** OPS-2 → OPS-1 → OPS-3. Supabase must be linked, migrated, and secrets synced before live cutover; notarization is independent of hosted cutover but ships last in the standard maintainer sequence.

Unified orchestrator: `./scripts/run-production-ops.sh` (wraps the individual scripts below).

---

## 1. Prerequisites

### 1.1 CI green on `main`

Confirm GitHub Actions is passing on the default branch before touching production:

- **`python-tests`** — full pytest suite
- **`product-gates`** — runs `./scripts/verify-ops-readiness.sh` (product gates, env template, cloud parity, cutover dry-run)
- **`hosted-preflight`** — Docker preflight + health probe
- **`postgres-tests`** — hosted Postgres / migration tests

See the CI coverage table in [tier2-hosted-web.md § Dry-run verification checklist](tier2-hosted-web.md#dry-run-verification-checklist-local-no-production-secrets).

### 1.2 Local ops-readiness (no production secrets)

From a clean checkout on `main`:

```bash
uv sync
./scripts/verify-ops-readiness.sh
```

This runs product gate tests, hosted env template gate, cloud parity fixtures, cloud load fixture, seed refresh audit, and an offline SQLite → Postgres cutover dry-run. It does **not** require `DATABASE_URL`, Supabase tokens, or Railway credentials.

Optional live health probe against a running local or preflight container:

```bash
BASE_URL=http://127.0.0.1:8765 ./scripts/verify-ops-readiness.sh
```

### 1.3 Maintainer tooling

| Tool | OPS | Install / login |
|------|-----|-----------------|
| **Supabase CLI** | OPS-2 | `brew install supabase/tap/supabase`; `supabase login` or `supabase login --token "$SUPABASE_ACCESS_TOKEN"` |
| **Railway CLI** | OPS-1, OPS-2 | [Railway CLI guide](https://docs.railway.com/guides/cli); `railway login` |
| **uv** | All | Project Python runner (`uv sync`) |
| **Xcode CLT + xcrun** | OPS-3 | macOS only; `xcode-select --install` |

---

## 2. Environment setup

### 2.1 Copy and fill credentials

```bash
cp .env.ops.example .env.ops.local
# Edit .env.ops.local — never commit this file
```

Load before running OPS scripts (adjust path if you use a different filename):

```bash
set -a
source .env.ops.local
set +a
```

Or export variables in your shell session. All OPS scripts read from the environment.

### 2.2 Preflight all OPS

Check which OPS are ready without running live changes:

```bash
./scripts/run-production-ops.sh --check-env
```

Individual script checks:

```bash
./scripts/bootstrap-supabase.sh --check-env
./scripts/sync-supabase-secrets.sh --check-env
./scripts/railway-cutover.sh --check-env
./scripts/notarize-macos-app.sh --require   # fails fast if Apple creds missing
```

### 2.3 Local dry-run (orchestrator)

Runs `verify-ops-readiness.sh` — same as §1.2, via the unified entrypoint:

```bash
./scripts/run-production-ops.sh --dry-run
```

Print recommended next commands without executing live OPS:

```bash
./scripts/run-production-ops.sh --all
```

---

## 3. OPS-2 — Supabase (run first)

**Goal:** Link project, apply migrations, prepare Storage, sync publishable and Phase B secrets to Railway.

### 3.1 Bootstrap (link + migrations)

Dry-run (prints planned commands, no changes):

```bash
./scripts/bootstrap-supabase.sh --dry-run
```

Live:

```bash
./scripts/bootstrap-supabase.sh
```

Or via orchestrator:

```bash
./scripts/run-production-ops.sh --ops-2
```

`--ops-2` runs bootstrap **and** Railway secret sync in one step.

### 3.2 Sync secrets

Writes `.env.supabase.local` and optionally pushes vars to Railway:

```bash
./scripts/sync-supabase-secrets.sh              # local file only
./scripts/sync-supabase-secrets.sh --railway    # push SUPABASE_URL, SUPABASE_ANON_KEY, and Phase B vars when set
```

Ensure `DATABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` are in your sourced env before `--railway` so Phase B vars sync to Railway.

### 3.3 Manual steps (Supabase dashboard)

The CLI cannot reliably create private Storage buckets. Complete these in the Supabase dashboard after bootstrap:

1. **Storage → New bucket**
   - Name: `resume-assets` (or match `ML_JOB_SWARM_RESUME_STORAGE_BUCKET`)
   - Public: **off** (private)
2. **SQL Editor** — run policies from `supabase/storage/resume-assets-policies.sql`
3. **Authentication → Providers → Email** — enable Email provider
4. **Project Settings → API** — copy full `SUPABASE_SERVICE_ROLE_KEY` if CLI output is masked; add to `.env.ops.local` and re-run sync

See [tier2-hosted-web.md § Deploy checklist — Supabase](tier2-hosted-web.md#1-supabase) for full detail.

---

## 4. OPS-1 — Railway Phase B cutover (run second)

**Goal:** Migrate exported hosted SQLite (`jobs.db`) and resume assets into Supabase Postgres/Storage, redeploy Railway, verify live.

**Prerequisites:** OPS-2 complete — migrations applied, bucket created, `DATABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY` on Railway (via sync script or dashboard).

### 4.1 Export hosted data

Export from the Railway volume (Phase A):

- `jobs.db` → set `ML_JOB_SWARM_SOURCE_DB`
- `resume-assets/` directory → set `ML_JOB_SWARM_RESUME_ASSET_DIR` (optional if no files)

### 4.2 Cutover dry-run

Offline validation (no live `DATABASE_URL` required):

```bash
./scripts/railway-cutover.sh --dry-run
```

Via orchestrator (passes through to `railway-cutover.sh`):

```bash
./scripts/run-production-ops.sh --ops-1 --dry-run
```

### 4.3 Live migration

Requires `DATABASE_URL` and a valid `ML_JOB_SWARM_SOURCE_DB`:

```bash
./scripts/railway-cutover.sh
```

Or:

```bash
./scripts/run-production-ops.sh --ops-1
```

### 4.4 Redeploy and smoke

After live migration, redeploy **web** and **worker** Railway services with Phase B env vars (see env table below).

Post-cutover smoke:

```bash
./scripts/railway-cutover.sh --smoke-only "${ML_JOB_SWARM_PUBLIC_URL}" "${ML_JOB_SWARM_ACCESS_TOKEN:-}"
```

Expect Postgres backend and Storage mode in `/healthz`. Full hosted smoke: `./scripts/smoke-postgres-cutover.sh` (documented in [tier2-hosted-web.md](tier2-hosted-web.md)).

### 4.5 Manual steps (Railway dashboard)

These are **not** fully scripted:

1. **Worker service** — create or configure a second Railway service from the same repo/image:
   - Set `ML_JOB_SWARM_PROCESS=worker`
   - Copy Phase B vars from web: `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `ML_JOB_SWARM_RESUME_STORAGE_BUCKET`
   - Phase B: shared volume **not** required (Postgres queue only)
   - See [tier2-hosted-web.md § Cloud worker](tier2-hosted-web.md#4-cloud-worker)

2. **Web service redeploy** — trigger redeploy after env var updates from OPS-2 sync

3. **Railway CLI absent** — if `railway` is not installed, set variables manually in Railway project → Variables (sync script prints the list)

4. **Optional Phase A volume** — after successful cutover, web may drop the `/data` volume dependency; confirm in dashboard

---

## 5. OPS-3 — Apple notarization (run third)

**Goal:** Codesign and notarize the packaged macOS app for Tier 3 distribution.

**Requires:** macOS host, Xcode command line tools, Apple Developer credentials, built app at `macos/dist/MLJobSwarm.app` (from `package-macos-release.sh`).

Preflight (exits 1 if creds missing):

```bash
./scripts/notarize-macos-app.sh --require
```

Live notarization via orchestrator:

```bash
./scripts/run-production-ops.sh --ops-3
```

Direct invocation with optional paths:

```bash
APP=macos/dist/MLJobSwarm.app ./scripts/notarize-macos-app.sh --require
```

Use either `NOTARYTOOL_PROFILE` (keychain profile from `xcrun notarytool store-credentials`) **or** the `APPLE_ID` + `APPLE_APP_SPECIFIC_PASSWORD` + `APPLE_TEAM_ID` trio — not both.

Set `CODESIGN_IDENTITY` to your **Developer ID Application** certificate for release builds.

See [tier3-app-stores.md § macOS — notarized distribution](tier3-app-stores.md#macos--notarized-distribution) for enrollment and CI secret guidance.

---

## 6. Full sequence (when env is complete)

Review only (check-env + printed steps):

```bash
./scripts/run-production-ops.sh --all
```

Execute OPS-2 → OPS-1 → OPS-3 in order (interactive maintainer action):

```bash
./scripts/run-production-ops.sh --execute-all
```

Recommended explicit flow:

```bash
# 1. Preflight
./scripts/run-production-ops.sh --check-env
./scripts/run-production-ops.sh --dry-run

# 2. OPS-2
./scripts/run-production-ops.sh --ops-2
# → complete Supabase dashboard steps (bucket, policies, Email auth)

# 3. OPS-1
./scripts/run-production-ops.sh --ops-1 --dry-run
./scripts/run-production-ops.sh --ops-1
# → redeploy Railway web + worker; smoke

# 4. OPS-3 (on macOS)
./scripts/run-production-ops.sh --ops-3
```

---

## 7. Environment variable reference

Source of truth: [`.env.ops.example`](../.env.ops.example). Copy to `.env.ops.local` and fill real values.

### OPS-2 — Supabase

| Variable | Required | Purpose |
|----------|----------|---------|
| `SUPABASE_PROJECT_REF` | Recommended | Dashboard → Project Settings → General; used by `supabase link` and sync |
| `SUPABASE_ACCESS_TOKEN` | For CI/non-interactive login | [Account tokens](https://supabase.com/dashboard/account/tokens); `supabase login --token` |
| `DATABASE_URL` | Phase B / OPS-1 | Session pooler URI; Database → Connection string |
| `SUPABASE_SERVICE_ROLE_KEY` | Phase B | Server-only secret (`sb_secret_...`); Storage uploads; sync to Railway |

### OPS-1 — Railway cutover

| Variable | Required | Purpose |
|----------|----------|---------|
| `ML_JOB_SWARM_SOURCE_DB` | Yes (live + dry-run) | Path to exported hosted `jobs.db` |
| `ML_JOB_SWARM_RESUME_ASSET_DIR` | Optional | Exported resume files from volume |
| `ML_JOB_SWARM_PUBLIC_URL` | Post-cutover smoke | Railway web URL (no trailing slash) |
| `ML_JOB_SWARM_ACCESS_TOKEN` | Optional | Bearer token for authenticated smoke endpoints |
| `SUPABASE_URL` | Phase B Railway | Synced via `sync-supabase-secrets.sh --railway` |
| `SUPABASE_ANON_KEY` | Phase B Railway | Publishable key; synced via `--railway` |
| `ML_JOB_SWARM_RESUME_STORAGE_BUCKET` | Phase B | Default `resume-assets`; web + worker |

**Worker-only (Railway dashboard):**

| Variable | Value |
|----------|-------|
| `ML_JOB_SWARM_PROCESS` | `worker` |

Additional hosted service variables (e.g. `OPENROUTER_API_KEY`, `ML_JOB_SWARM_PUBLIC_URL`) are cataloged in `.env.hosted.example` and [tier2-hosted-web.md](tier2-hosted-web.md).

### OPS-3 — Apple notarization

| Variable | Required | Purpose |
|----------|----------|---------|
| `NOTARYTOOL_PROFILE` | One auth method | Keychain profile for `notarytool` |
| `APPLE_ID` | Alternative to profile | Developer account email |
| `APPLE_APP_SPECIFIC_PASSWORD` | With `APPLE_ID` | App-specific password |
| `APPLE_TEAM_ID` | With `APPLE_ID` | 10-character Team ID |
| `CODESIGN_IDENTITY` | Release builds | e.g. `Developer ID Application: Your Name (TEAMID)`; `-` for ad-hoc |

---

## 8. Manual vs scripted summary

| Step | Scripted | Manual (dashboard / maintainer) |
|------|----------|----------------------------------|
| Supabase link + `db push` | `bootstrap-supabase.sh` | — |
| Private Storage bucket | — | Supabase Storage dashboard |
| Storage RLS policies | — | Supabase SQL Editor (`resume-assets-policies.sql`) |
| Email auth provider | — | Supabase Authentication dashboard |
| Fetch/sync API keys | `sync-supabase-secrets.sh` | Copy full service role if CLI masks secret |
| Railway env vars | `sync-supabase-secrets.sh --railway` | Railway Variables if no CLI |
| SQLite → Postgres migration | `railway-cutover.sh` | Export volume data first |
| Railway web redeploy | — | Railway dashboard or `railway up` |
| Railway **worker** service | — | Second service, `ML_JOB_SWARM_PROCESS=worker` |
| Post-cutover smoke | `railway-cutover.sh --smoke-only` | — |
| macOS codesign + notarize | `notarize-macos-app.sh --require` | Apple Developer enrollment, cert, macOS host |

---

## 9. Troubleshooting

| Symptom | Action |
|---------|--------|
| `--check-env` reports OPS-2 blocked | Install Supabase CLI; run `supabase login`; set `SUPABASE_ACCESS_TOKEN` if non-interactive |
| `--check-env` reports OPS-1 blocked | Set `DATABASE_URL` and `ML_JOB_SWARM_SOURCE_DB` pointing at a real export file |
| `--check-env` reports OPS-3 blocked | Run on macOS; set `NOTARYTOOL_PROFILE` or Apple ID trio |
| `sync-supabase-secrets.sh --railway` skips push | Install Railway CLI and `railway login`, or set vars manually in dashboard |
| Live cutover fails on Storage | Confirm private bucket exists and policies SQL applied (§3.3) |
| Smoke fails after cutover | Redeploy web + worker with Phase B vars; verify `DATABASE_URL` pooler URI |

For architecture and per-service variable detail, see [tier2-hosted-web.md](tier2-hosted-web.md). For notarization and store strategy, see [tier3-app-stores.md](tier3-app-stores.md).
