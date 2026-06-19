# Product distribution tiers

| Tier | Goal | Status |
|------|------|--------|
| 1 | GitHub downloaders — macOS app anyone can install | **Complete** |
| 2 | Hosted webapp (Railway + Supabase) | **Phase B code complete** (production cutover pending) |
| 3 | App Store (Apple + Android) | **Planned** — see [tier3-app-stores.md](tier3-app-stores.md) |

## Tier 1 — complete

Public distribution lives in [davidlifschitz/job-swarm](https://github.com/davidlifschitz/job-swarm).

**Install**

```bash
brew tap davidlifschitz/job-swarm https://github.com/davidlifschitz/job-swarm
brew trust davidlifschitz/job-swarm
brew install --cask ml-job-swarm
```

**Maintainer release**

1. `uv run pytest -q`
2. Tag `v*.*.*` on `main`
3. GitHub Actions builds tar.gz, publishes the release, and bumps `Casks/ml-job-swarm.rb` on `main`

See [tier1-macos-release.md](tier1-macos-release.md) for details.

## Tier 2 — hosted web

Deploy the FastAPI web UI and cloud runtime to Railway with Supabase Auth.

**Phase A (complete):** Railway + Supabase Auth + volume-backed SQLite + per-user isolation.

**Phase B (code complete):** Supabase Postgres + Storage, migration tooling (`migrate-hosted`), cutover smoke — see [tier2-hosted-web.md](tier2-hosted-web.md).

**Production cutover:** set `DATABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY` on Railway web + worker, run `./scripts/railway-cutover.sh`, verify with `smoke-postgres-cutover.sh`.

Cloud SLO hardening remains in [cloud-production-server-goals.md](cloud-production-server-goals.md).

## Tier 3 — app stores

Notarized macOS + Apple Developer Program; Android native or installable PWA. See [tier3-app-stores.md](tier3-app-stores.md).