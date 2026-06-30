# OPS Production Packaging Plan

**Active goal:** Make OPS-1–3 code-prepared with unified maintainer orchestration, env preflight, and tests — executable when credentials are present; honest `--check-env` when not.

**Depends on:** W9–W13 merged (PR #6 on `main`).

---

## Dependency graph

```
W14a (parallel, disjoint files)
  → W14b (run-production-ops.sh + tests — depends lib + script flags)
  → W14c (docs + plan checkbox sync — docs only)
```

---

## Wave 14a — OPS script hardening (parallel)

- [x] **W14a-T1 ops-env-check library**
  - **Owns:** `scripts/lib/ops-env-check.sh` (new)
  - **Do NOT touch:** other scripts
  - **Subagent:** generalPurpose / composer-2.5-fast
  - **Acceptance:** Sources cleanly; exports `ops_check_ops1`, `ops_check_ops2`, `ops_check_ops3`, `ops_report_missing`

- [x] **W14a-T2 .env.ops.example**
  - **Owns:** `.env.ops.example` (new)
  - **Do NOT touch:** `.env.hosted.example`, code
  - **Subagent:** generalPurpose / composer-2.5-fast
  - **Acceptance:** Documents all OPS-1/2/3 maintainer vars; referenced in git via `!.env.ops.example` if needed

- [x] **W14a-T3 bootstrap-supabase.sh**
  - **Owns:** `scripts/bootstrap-supabase.sh` (new)
  - **Do NOT touch:** sync-supabase-secrets.sh, railway scripts
  - **Subagent:** generalPurpose / composer-2.5-fast
  - **Acceptance:** `--check-env` + `--dry-run` modes; documents link/db push/bucket steps; exits 0 on dry-run

- [x] **W14a-T4 railway-cutover --check-env**
  - **Owns:** `scripts/railway-cutover.sh` only
  - **Do NOT touch:** other scripts
  - **Subagent:** generalPurpose / composer-2.5-fast
  - **Acceptance:** `./scripts/railway-cutover.sh --check-env` lists missing vars, exit 1 if live cutover blocked

- [x] **W14a-T5 notarize --require flag**
  - **Owns:** `scripts/notarize-macos-app.sh` only
  - **Do NOT touch:** other scripts
  - **Subagent:** generalPurpose / composer-2.5-fast
  - **Acceptance:** `--require` exits 1 when creds missing; default skip behavior unchanged

- [x] **W14a-T6 sync-supabase --check-env**
  - **Owns:** `scripts/sync-supabase-secrets.sh` only
  - **Do NOT touch:** other scripts
  - **Subagent:** generalPurpose / composer-2.5-fast
  - **Acceptance:** `--check-env` reports CLI login + optional Phase B vars; `--railway` accepts DATABASE_URL/SERVICE_ROLE from env when set

---

## Wave 14b — Unified maintainer orchestrator

- [ ] **W14b-T1 run-production-ops.sh**
  - **Owns:** `scripts/run-production-ops.sh` (new)
  - **Do NOT touch:** existing script internals (delegate only)
  - **Subagent:** generalPurpose
  - **Acceptance:** Subcommands `--check-env`, `--dry-run`, `--ops-1`, `--ops-2`, `--ops-3`; `--dry-run` runs verify-ops-readiness.sh

- [ ] **W14b-T2 production ops tests**
  - **Owns:** `tests/test_run_production_ops_script.py`, `tests/test_notarize_macos_app_script.py` (new)
  - **Do NOT touch:** production scripts except read-only
  - **Subagent:** generalPurpose
  - **Acceptance:** `uv run pytest` green for new tests

---

## Wave 14c — Docs and plan closure

- [ ] **W14c-T1 maintainer production ops doc**
  - **Owns:** `docs/maintainer-production-ops.md` (new)
  - **Do NOT touch:** code
  - **Subagent:** generalPurpose
  - **Acceptance:** Ordered OPS-2 → OPS-1 → OPS-3 runbook with env table + script commands

- [ ] **W14c-T2 Plan checkbox sync**
  - **Owns:** `docs/superpowers/plans/2026-06-30-job-swarm-final-completion.md`, `docs/superpowers/plans/2026-06-29-job-swarm-completion-orchestration.md` (OPS section only), `docs/superpowers/plans/README.md` (one row)
  - **Do NOT touch:** application code
  - **Subagent:** orchestrator
  - **Acceptance:** OPS marked code-prepared; maintainer execution note retained

---

## OPS acceptance (final)

| ID | Code-prepared | Live execution |
|----|---------------|----------------|
| OPS-1 | `run-production-ops.sh --ops-1` delegates to cutover when env set | Maintainer `DATABASE_URL` + export |
| OPS-2 | `bootstrap-supabase.sh` + `sync-supabase-secrets.sh` | Supabase CLI login |
| OPS-3 | `notarize-macos-app.sh --require` | Apple Developer creds on macOS |

**Done:** All checklist items `[x]`; `uv run pytest -q` green; `./scripts/run-production-ops.sh --check-env` runs.
