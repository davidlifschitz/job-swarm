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

- [ ] **W11a-T1 seed_refresh_audit live evaluate CLI**
  - **Owns:** `scripts/seed_refresh_audit.py`, `tests/test_seed_refresh_audit.py`
  - **Do NOT touch:** workflows, other scripts
  - **Subagent:** generalPurpose
  - **Acceptance:** `--evaluate-live` (or equivalent) replaces inline workflow Python; pytest green

---

## Wave 11b — Nightly workflow DRY

- [ ] **W11b-T1 nightly-seed-audit.yml uses CLI**
  - **Owns:** `.github/workflows/nightly-seed-audit.yml`
  - **Do NOT touch:** application code, seed_refresh_audit.py
  - **Subagent:** generalPurpose
  - **Acceptance:** Evaluate step calls script; remove unused `actions: write`; upload tolerates partial failure

---

## Wave 12 — UI performance gate

- [ ] **W12-T1 UI render p95 smoke test**
  - **Owns:** `tests/test_ui_performance_gate.py` (new), `tests/support/ui_perf_seed.py` (new if needed)
  - **Do NOT touch:** `app.py`, templates, production routes
  - **Subagent:** generalPurpose
  - **Acceptance:** Seeded 500 jobs / 50 sources fixture; dashboard/job detail/saved jobs/admin p95 ≤ 1s; pytest green

---

## Wave 13 — Final orchestration sync

- [ ] **W13-T1 Mark all waves complete in orchestration plans**
  - **Owns:** `docs/superpowers/plans/2026-06-29-job-swarm-completion-orchestration.md`, `docs/superpowers/plans/2026-06-30-job-swarm-final-completion.md`
  - **Do NOT touch:** application code
  - **Subagent:** orchestrator (integration)
  - **Acceptance:** All W9–W12 marked [x]; local verification table current; full pytest green

---

## Ops-only (maintainer credentials required)

- [ ] **OPS-1** Railway Phase B cutover (`DATABASE_URL`, migration, worker service)
- [ ] **OPS-2** Supabase bucket + secret rotation
- [ ] **OPS-3** Apple notarization / Tier 3

**Code-prepared acceptance:** `verify-ops-readiness.sh` + CI `product-gates` + `hosted-preflight` green; maintainer steps documented in `docs/tier2-hosted-web.md`.

---

## Completion status

W1–W8: **complete**. W9–W13: **in progress**.
