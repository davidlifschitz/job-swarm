# Job Swarm Final Completion Orchestration Plan

**Active goal:** Close all remaining ml-job-swarm gaps (doc drift, CI preflight/health probe, env template gate, nightly audit DRY, UI perf gate, ops maintainer packaging) so code/CI/docs are fully complete; OPS-1–3 remain maintainer-executed with production credentials.

**Source of truth:** This checklist. Update after every wave.

**Prior work:** Waves W1–W8 complete on `main` (`08ae122`). PR #5 merged — `product-gates` runs `verify-ops-readiness.sh`.

---

## Dependency graph

```
W9 (doc sync — disjoint doc files, parallel)
  → W10a (env template test + CI preflight job — parallel, disjoint)
  → W10b (verify-ops-readiness env step — depends W10a-T1)
  → W11a (seed_refresh_audit live CLI — scripts/tests only)
  → W11b (nightly workflow uses CLI — depends W11a)
  → W12 (UI perf gate — tests only)
  → W13 (orchestration plan + status HTML final sync — single task)
```

OPS-1–3: production secrets required; acceptance = maintainer runbook + `verify-ops-readiness.sh` green + ops script documents required env vars.

---

## Wave 9 — Doc sync (parallel, disjoint files)

- [x] **W9-T1 E2E readiness doc drift**
  - **Owns:** `docs/superpowers/e2e-product-readiness.md`
  - **Do NOT touch:** code, other docs
  - **Subagent:** generalPurpose
  - **Acceptance:** No stale "on branch" / "after merge" pending text; nightly audit evidence reflects merged workflow on main; test count ~531

- [x] **W9-T2 Plan index doc drift**
  - **Owns:** `docs/superpowers/plans/README.md`
  - **Do NOT touch:** code, other docs
  - **Subagent:** generalPurpose
  - **Acceptance:** Nightly seed audit marked on main; PR #5 CI wiring noted

- [x] **W9-T3 Tier 2 runbook CI coverage notes**
  - **Owns:** `docs/tier2-hosted-web.md` (dry-run checklist section only)
  - **Do NOT touch:** code, workflows
  - **Subagent:** generalPurpose
  - **Acceptance:** Steps 2–4 and 8 document which are CI-covered vs local-only (honest pre-W10)

- [x] **W9-T4 Status HTML refresh**
  - **Owns:** `tmp/job-swarm-completion-status.html`
  - **Do NOT touch:** application code
  - **Subagent:** generalPurpose
  - **Acceptance:** Reflects PRs #1–#5 merged, main HEAD, remaining ops-only work

---

## Wave 10a — CI preflight + env template test (parallel)

- [x] **W10a-T1 Hosted env template gate test**
  - **Owns:** `tests/test_hosted_env_template.py` (new)
  - **Do NOT touch:** `.env.hosted.example`, docs, workflows
  - **Subagent:** generalPurpose
  - **Acceptance:** `uv run pytest tests/test_hosted_env_template.py -q` green; keys match `docs/tier2-hosted-web.md` deploy tables

- [x] **W10a-T2 CI hosted-preflight job**
  - **Owns:** `.github/workflows/ci.yml` (add `hosted-preflight` job only)
  - **Do NOT touch:** application code, scripts, other jobs' steps
  - **Subagent:** generalPurpose
  - **Acceptance:** Job runs `railway-preflight.sh`, then `cloud-health-probe.sh` with `BASE_URL`; YAML valid

---

## Wave 10b — verify-ops-readiness env step

- [x] **W10b-T1 Wire env template into verify-ops-readiness**
  - **Owns:** `scripts/verify-ops-readiness.sh`, `tests/test_verify_ops_readiness_script.py`
  - **Do NOT touch:** `ci.yml`, `test_hosted_env_template.py`
  - **Subagent:** generalPurpose
  - **Acceptance:** Script runs env template pytest; full script + pytest green

---

## Wave 11a — Nightly audit CLI extraction

- [x] **W11a-T1 seed_refresh_audit live evaluate CLI**
  - **Owns:** `scripts/seed_refresh_audit.py`, `tests/test_seed_refresh_audit.py`
  - **Do NOT touch:** workflows, other scripts
  - **Subagent:** generalPurpose
  - **Acceptance:** `--evaluate-live` (or equivalent) replaces inline workflow Python; pytest green

---

## Wave 11b — Nightly workflow DRY

- [x] **W11b-T1 nightly-seed-audit.yml uses CLI**
  - **Owns:** `.github/workflows/nightly-seed-audit.yml`
  - **Do NOT touch:** application code, seed_refresh_audit.py
  - **Subagent:** generalPurpose
  - **Acceptance:** Evaluate step calls script; remove unused `actions: write`; upload tolerates partial failure

---

## Wave 12 — UI performance gate

- [x] **W12-T1 UI render p95 smoke test**
  - **Owns:** `tests/test_ui_performance_gate.py` (new), `tests/support/ui_perf_seed.py` (new if needed)
  - **Do NOT touch:** `app.py`, templates, production routes
  - **Subagent:** generalPurpose
  - **Acceptance:** Seeded 500 jobs / 50 sources fixture; dashboard/job detail/saved jobs/admin p95 ≤ 1s; pytest green

---

## Wave 13 — Final orchestration sync

- [x] **W13-T1 Mark all waves complete in orchestration plans**
  - **Owns:** `docs/superpowers/plans/2026-06-29-job-swarm-completion-orchestration.md`, `docs/superpowers/plans/2026-06-30-job-swarm-final-completion.md`
  - **Do NOT touch:** application code
  - **Subagent:** orchestrator (integration)
  - **Acceptance:** All W9–W12 marked [x]; local verification table current; full pytest green

---

## Ops-only (maintainer live execution)

Code-prepared (W14, PR #7): scripts, env template, and runbook ready. Live execution requires maintainer credentials.

- [x] **OPS-1 code-prepared** — `railway-cutover.sh --check-env`, `run-production-ops.sh --ops-1`
- [x] **OPS-2 code-prepared** — `bootstrap-supabase.sh`, `sync-supabase-secrets.sh --check-env --railway`
- [x] **OPS-3 code-prepared** — `notarize-macos-app.sh --require`, `run-production-ops.sh --ops-3`
- [ ] **OPS-1 live** — maintainer runs cutover with `DATABASE_URL` + SQLite export
- [ ] **OPS-2 live** — maintainer Supabase login + bucket + secret rotation
- [ ] **OPS-3 live** — maintainer Apple notarization on macOS release

**Maintainer runbook:** [`docs/maintainer-production-ops.md`](../../maintainer-production-ops.md) · **Preflight:** `./scripts/run-production-ops.sh --check-env` and `--dry-run`

---

## Completion status

W1–W8: **complete** on `main`. W9–W13: **complete** (PR #6). W14 OPS packaging: **complete** (PR #7).

All agent-executable work is **done**. OPS live execution is **maintainer-only** with production credentials.

### Local verification (2026-06-30)

| Check | Result |
| --- | --- |
| `uv run pytest -q` | 543 passed, 12 skipped |
| `./scripts/verify-ops-readiness.sh` | pass |
| `./scripts/run-production-ops.sh --check-env` | reports missing creds (expected locally) |
| `./scripts/run-production-ops.sh --dry-run` | pass |
| CI jobs | `python-tests`, `product-gates`, `hosted-preflight`, `postgres-tests`, `cloud-parity`, `docker-build`, `macos-build`, nightly seed audit |
| PRs #1–#6 merged on main | `dd695dd` + OPS packaging PR #7 pending |
