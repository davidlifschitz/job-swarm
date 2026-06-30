# Job Swarm Completion Orchestration Plan

**Active goal:** Close remaining ml-job-swarm gaps (hosted cutover readiness, cloud operator UI, quantitative gates, cloud SLO code, doc/CI hygiene) with parallel subagents and wave integration.

**Source of truth:** This checklist. Update after every wave.

---

## Dependency graph (summary)

```
W1 (metrics/gates/fixtures, no app.py)
  → W2 (cloud operator UI — owns app.py + templates)
  → W3 (cloud SLO code — cloud_runtime.py + scripts)
  → W4 (CI workflows — .github only)
  → W5 (docs/index — docs only)
```

Ops-only items (Railway/Supabase live cutover, notarization secrets) → runbook + dry-run verification only.

---

## Wave 1 — Quantitative gates & hosted env template (parallel, no shared files)

- [x] **W1-T1 Product metrics evaluator**
  - **Owns:** `ml_job_swarm/product_goals.py`, `tests/test_product_goals.py`
  - **Do NOT touch:** `app.py`, workflows, templates
  - **Subagent:** generalPurpose
  - **Acceptance:** `evaluate_product_metrics()` returns violations on bad input, empty on good; `uv run pytest tests/test_product_goals.py -q` green

- [x] **W1-T2 Seed policy gate test**
  - **Owns:** `tests/test_seed_policy_gate.py` (new)
  - **Do NOT touch:** `data/seed_companies.json`, `app.py`
  - **Subagent:** generalPurpose
  - **Acceptance:** Asserts 82 seed sources all classified with next_action; `pytest tests/test_seed_policy_gate.py -q` green

- [x] **W1-T3 Offline seed refresh audit**
  - **Owns:** `scripts/seed_refresh_audit.py` (new), `tests/test_seed_refresh_audit.py` (new)
  - **Do NOT touch:** `app.py`, `product_goals.py`
  - **Subagent:** generalPurpose
  - **Acceptance:** Fixture-dir refresh audit exits 0; pytest green; JSON includes attempted/succeeded/failure reasons

- [x] **W1-T4 Golden profile matching gate**
  - **Owns:** `tests/fixtures/golden_profiles/` (new), `tests/test_golden_profile_matching.py` (new)
  - **Do NOT touch:** `filtering.py` unless absolutely required; prefer test-only helpers
  - **Subagent:** generalPurpose
  - **Acceptance:** ≥80% top-20 match on fixture; all rows have reasons; pytest green

- [x] **W1-T5 Catalog quality gate**
  - **Owns:** `tests/test_catalog_quality_gate.py` (new)
  - **Do NOT touch:** `product_goals.py`, `app.py`
  - **Subagent:** generalPurpose
  - **Acceptance:** Controlled fixture DB passes duplicate/stale thresholds; pytest green

- [x] **W1-T6 Hosted env template**
  - **Owns:** `.env.hosted.example` (new)
  - **Do NOT touch:** production secrets, Railway config
  - **Subagent:** generalPurpose
  - **Acceptance:** File exists with all Phase B vars documented; referenced vars match `docs/tier2-hosted-web.md`

---

## Wave 2 — Cloud operator UI (single task — shared app.py/templates)

- [x] **W2-T1 Cloud operator HTML console**
  - **Owns:** `ml_job_swarm/app.py` (cloud UI block only), `ml_job_swarm/web/templates/cloud_runs.html`, `cloud_run_detail.html`, `dashboard.html`, `base.html`, `app.css`, `tests/test_routes_cloud_ui.py`
  - **Do NOT touch:** `/api/cloud/*` JSON handlers, `cloud_runtime.py`, `cloud_worker.py`, admin ingestion runs
  - **Subagent:** generalPurpose
  - **Acceptance:** Dashboard shows active cloud run; `/cloud/runs` list + detail; cancel/start forms; auth scoping; `pytest tests/test_routes_cloud_ui.py -q` green

---

## Wave 3 — Cloud SLO code (parallel, disjoint files)

- [x] **W3-T1 Structured cloud logging schema**
  - **Owns:** `ml_job_swarm/cloud_logging.py` (new), `tests/test_cloud_logging_schema.py` (new), `ml_job_swarm/cloud_runtime.py` (logging hooks in `_append_event`/`_set_run_state` only)
  - **Do NOT touch:** `app.py`, worker loop
  - **Subagent:** generalPurpose
  - **Acceptance:** Every state transition emits schema-valid log dict; pytest green

- [x] **W3-T2 Runtime parity fixtures**
  - **Owns:** `tests/fixtures/cloud_parity/` (new), `tests/test_cloud_runtime_parity_fixtures.py` (new), `scripts/run-cloud-parity-check.sh` (new)
  - **Do NOT touch:** `cloud_runtime.py`
  - **Subagent:** generalPurpose
  - **Acceptance:** Parity check passes on committed baseline; script exits 0

- [x] **W3-T3 Cloud load capacity fixture**
  - **Owns:** `tests/support/cloud_load_seed.py` (new), `tests/test_cloud_load_capacity.py` (new), `scripts/run-cloud-load-test.py` (new)
  - **Do NOT touch:** `app.py`, `cloud_runtime.py`
  - **Subagent:** generalPurpose
  - **Acceptance:** 10 concurrent queued runs drain without duplicate packets; pytest green

- [x] **W3-T4 Health probe script**
  - **Owns:** `scripts/cloud-health-probe.sh` (new), `tests/test_cloud_health_probe_script.py` (new)
  - **Do NOT touch:** `app.py`
  - **Subagent:** generalPurpose
  - **Acceptance:** Script measures /healthz p95 against SLO_TARGETS; pytest validates script logic

- [x] **W3-T5 Error-state & observability gate tests**
  - **Owns:** `tests/test_error_handling_gates.py` (new), `tests/test_operator_observability_gate.py` (new)
  - **Do NOT touch:** `app.py` unless tests prove missing audit — then fix in Wave 3 integration pass
  - **Subagent:** generalPurpose
  - **Acceptance:** Matrix tests for next-action + audit redaction; pytest green

---

## Wave 4 — CI workflows (parallel, .github only)

- [x] **W4-T1 Product gates CI job**
  - **Owns:** `.github/workflows/ci.yml` (add job/step only)
  - **Do NOT touch:** application code
  - **Subagent:** generalPurpose
  - **Acceptance:** CI runs gate tests subset; workflow YAML valid

- [x] **W4-T2 Nightly live seed audit workflow**
  - **Owns:** `.github/workflows/nightly-seed-audit.yml` (new)
  - **Do NOT touch:** application code
  - **Subagent:** generalPurpose
  - **Acceptance:** Scheduled workflow runs live refresh + uploads artifact; uses existing CLI

- [x] **W4-T3 Cloud parity CI workflow**
  - **Owns:** `.github/workflows/cloud-parity.yml` (new)
  - **Do NOT touch:** application code
  - **Subagent:** generalPurpose
  - **Acceptance:** Workflow runs parity script + pytest on PR/push

---

## Wave 5 — Documentation & ops runbooks (parallel, docs only)

- [x] **W5-T1 Update plan index & e2e readiness**
  - **Owns:** `docs/superpowers/plans/README.md`, `docs/superpowers/e2e-product-readiness.md`
  - **Do NOT touch:** code
  - **Subagent:** generalPurpose
  - **Acceptance:** New slices documented; test count evidence updated

- [x] **W5-T2 Tier 2 cutover runbook verification section**
  - **Owns:** `docs/tier2-hosted-web.md` (append verification checklist only)
  - **Do NOT touch:** code
  - **Subagent:** generalPurpose
  - **Acceptance:** Dry-run commands documented; ops-only steps clearly marked

---

## Wave 6 — Doc sync & local ops verification (parallel)

- [x] **W6-T1 Doc drift fix (nightly audit → Done)**
  - **Owns:** `docs/superpowers/e2e-product-readiness.md`, `docs/superpowers/plans/README.md`, `docs/tier2-hosted-web.md` (ops bullet only)
  - **Do NOT touch:** code, workflows
  - **Subagent:** generalPurpose
  - **Acceptance:** No stale "W4-T2 pending" or "workflow not committed" text

- [x] **W6-T2 Local ops dry-run verification**
  - **Owns:** `docs/superpowers/plans/2026-06-29-job-swarm-completion-orchestration.md` (OPS verification section only)
  - **Do NOT touch:** application code
  - **Subagent:** generalPurpose
  - **Acceptance:** Records results of pytest, parity script, seed audit, migrate dry-run; marks OPS runbook verified locally

---

## Wave 7 — Merge to main (single task)

- [x] **W7-T1 Merge PR #1**
  - **Owns:** GitHub PR #1 only (merge operation)
  - **Do NOT touch:** code unless CI fails on merge queue
  - **Subagent:** orchestrator (gh pr ready + gh pr merge)
  - **Acceptance:** PR merged to main; branch CI green on head commit

---

## Wave 8 — Post-merge verification (single task)

- [x] **W8-T1 Verify main + update checklist**
  - **Owns:** `docs/superpowers/plans/2026-06-29-job-swarm-completion-orchestration.md`, `tmp/job-swarm-completion-status.html`
  - **Acceptance:** `git checkout main && pull`; pytest green; orchestration plan marks W6-W8 complete; OPS marked runbook-verified

---

## Ops-only (production execution — blocked on secrets)

- [ ] **OPS-1** Railway Phase B cutover (DATABASE_URL, migration, worker service)
- [ ] **OPS-2** Supabase bucket + secret rotation
- [ ] **OPS-3** Apple notarization / Tier 3

**Acceptance for ops:** Runbook + dry-run scripts pass locally (**W6-T2**); production steps documented for maintainer.

### Local ops verification (2026-06-30)

| Check | Result |
| --- | --- |
| `uv run pytest -q` on `main` | 530 passed, 12 skipped |
| `./scripts/run-cloud-parity-check.sh` | pass |
| `uv run python scripts/run-cloud-load-test.py` | pass |
| `uv run ml-job-swarm migrate-hosted --dry-run` | pass |
| PR #1 merged | `c6b4b47` on `main` |

**OPS runbook verified locally.** OPS-1–3 production execution remains blocked on maintainer credentials.

---

## Completion status

All code waves **W1–W8 complete**. Remaining work is **ops-only** (Railway/Supabase/Apple secrets).
