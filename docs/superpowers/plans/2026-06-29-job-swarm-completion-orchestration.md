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

- [ ] **W4-T2 Nightly live seed audit workflow**
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

## Ops-only (cannot complete without production secrets)

- [ ] **OPS-1** Railway Phase B cutover (DATABASE_URL, migration, worker service)
- [ ] **OPS-2** Supabase bucket + secret rotation
- [ ] **OPS-3** Apple notarization / Tier 3

**Acceptance for ops:** Runbook + dry-run scripts pass locally; production steps documented for maintainer.

---

## Integration gates (after each wave)

1. `uv run pytest -q` — full suite green
2. Fix any integration breakage before next wave
3. Commit + push on branch `cursor/job-swarm-completion-a771`
