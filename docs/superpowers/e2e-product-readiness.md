# E2E Product Readiness

This is the canonical checklist for making the website a real V1 product rather
than a stub. New work should update this file or the linked plan index so agents
do not repeat completed slices.

Final-product quantitative targets live in
`specs/2026-05-14-final-product-quantitative-goals-design.md`. Treat that spec
as the measurable bar for future slices, even when this readiness table marks
the current V1 surface as done.

| Area | Status | Owner Plan | Evidence | Last Verified |
| --- | --- | --- | --- | --- |
| First-run app shell and onboarding | Done | `plans/2026-05-11-product-grade-first-run.md` | Local app has onboarding guidance, deployment status, and admin source health polish. | 2026-05-11 |
| Resume upload and local parse | Done | `plans/2026-05-08-job-catalog-resume-matching.md` | PDF/DOCX parse routes and low-confidence vision fallback consent are covered by route tests. | 2026-05-11 |
| Seeded public source catalog | Done | `plans/2026-05-10-runtime-seeded-app.md` | `create_app_from_env` imports `data/seed_companies.json` idempotently. | 2026-05-11 |
| Live public source refresh | Done | `plans/2026-05-11-refresh-summary-truth.md` | Refresh summaries distinguish attempted vs succeeded sources in focused route/ingest tests. | 2026-05-11 |
| Rules-first matching without LLM | Done | `plans/2026-05-08-job-catalog-resume-matching.md` | Dashboard renders rules preview when jobs and a target profile exist. | 2026-05-11 |
| Consent-gated LLM fit review | Done | `plans/2026-05-10-web-job-review.md` | Fit-review routes require consent and configured client. | 2026-05-11 |
| Saved jobs and CSV export | Done | `plans/2026-05-11-refresh-summary-truth.md` | Saved jobs include no-LLM public-refresh jobs with `Not reviewed` fit status. | 2026-05-11 |
| Application packet prep | Done | `plans/2026-05-10-application-prep-workspace.md`, `plans/2026-05-11-application-packet-integrity.md` | Saved/detail pages prepare local packets for manual submit, preserve submitted packet status, and carry accepted resume rewrites into the packet. | 2026-05-11 |
| Admin source friction and audit | Done | `plans/2026-05-10-source-friction-log.md` | Friction events, review actions, audit events, and CSV exports exist. | 2026-05-11 |
| Recovered source health | Done | `plans/2026-05-11-source-health-recovery.md` | Current source health suppresses stale friction after a later successful refresh while friction history remains available. | 2026-05-11 |
| Source health labels | Done | `plans/2026-05-11-source-health-labels.md` | Admin source rows show adapter readiness separately from unchecked, healthy, needs-review, no-adapter, and disabled health states. | 2026-05-11 |
| Durable live E2E smoke | Done | `plans/2026-05-11-live-e2e-smoke-script.md`, `plans/2026-05-11-live-e2e-smoke-operator-logs.md` | `scripts/live_e2e_smoke.py` runs DOCX upload, profile, live public refresh, save, Saved Jobs, and packet prep against one public Anthropic seed, with screenshots and `uvicorn.log` artifacts. | 2026-05-11 |
| Deployment truth | Done | `plans/2026-05-11-product-grade-first-run.md` | UI reports local vs configured public URL honestly. | 2026-05-11 |
| Cloud production runtime baseline | Done | `../cloud-production-server-goals.md` | JSON cloud-run API persists lifecycle state, emits run events, gates sources through source policy, executes queued or create-and-run cloud workflows through refresh/matching/packet-prep worker stages, records packet manifests, supports heartbeat/cancel, reports health/readiness, ships a queue-draining worker command, compares parity fixtures, redacts sensitive payloads, and blocks automated final submit. | 2026-05-14 |
| Quantitative product gates | Done | `specs/2026-05-14-final-product-quantitative-goals-design.md` | `ml_job_swarm/product_goals.py` measures seed-source classification, smoke metrics, next-action coverage, manual-submit boundary, referral alias precision, and catalog quality; live smoke emits `product_metrics`. | 2026-05-14 |
| Cloud operator UI | Done | `plans/2026-06-29-job-swarm-completion-orchestration.md` | Dashboard shows active cloud run; `/cloud/runs` list + detail pages; cancel/start forms; JWT user scoping. `uv run pytest tests/test_routes_cloud_ui.py -q` green. | 2026-06-29 |
| Product gate CI | Done | `plans/2026-06-29-job-swarm-completion-orchestration.md` | `.github/workflows/ci.yml` `product-gates` job runs seed-policy, golden-profile, catalog-quality, seed-refresh-audit, and observability gate tests on PR/push. | 2026-06-29 |
| Nightly seed audit (scheduled) | Done | `plans/2026-06-29-job-swarm-completion-orchestration.md` | Offline `scripts/seed_refresh_audit.py` + `tests/test_seed_refresh_audit.py` pass locally; `.github/workflows/nightly-seed-audit.yml` committed on branch (06:00 UTC cron + `workflow_dispatch`); first scheduled run after merge to default branch. | 2026-06-30 |
| Runtime parity fixtures | Done | `plans/2026-06-29-job-swarm-completion-orchestration.md` | `tests/fixtures/cloud_parity/` baseline; `scripts/run-cloud-parity-check.sh` and `.github/workflows/cloud-parity.yml` run `tests/test_cloud_runtime_parity_fixtures.py` on PR/push. | 2026-06-29 |

## V1 Done Definition

A local user can start the app, upload a resume, create a target profile,
refresh reviewed public sources, see real job rows from supported public sources,
review rules-first matches, save jobs, prepare a local manual-submit packet, and
inspect source health/friction without credentials, hidden browser sessions,
LinkedIn/Indeed scraping, CAPTCHA bypass, or automatic final submission.

## Latest Evidence

- 2026-05-11: `uv run pytest -q` -> 395 passed.
- 2026-05-11: Browser smoke against live Anthropic Greenhouse seed refreshed
  422 jobs, saved a no-LLM job, and prepared a manual-submit packet.
- 2026-05-11: Recovered source health route test proves stale friction is
  hidden from current health while remaining in friction history.
- 2026-05-11: Source health label route tests cover unchecked, healthy, and
  needs-review states.
- 2026-05-11: `uv run --with uvicorn --with playwright python
  scripts/live_e2e_smoke.py` -> `browser_e2e_ok`, 422 live jobs,
  progress output, screenshots, and `server_log_path`.
- 2026-05-11: `uv run pytest tests/test_routes_onboarding.py -q -k
  "application_packet"` -> 7 passed for packet status and accepted resume
  rewrite handling.
- 2026-05-11: Live smoke after packet integrity changes -> `browser_e2e_ok`,
  422 live jobs, packet prep completed.
- 2026-05-14: `uv run python -m pytest -q` -> 416 passed, including cloud
  runtime contract, source-policy gate, packet manifest, health/readiness,
  restart recovery, redaction, heartbeat/cancel, and final-submit boundary
  route tests.
- 2026-05-14: Cloud worker tests prove `POST /api/cloud/worker/run-next`
  executes queued runs through public source refresh, rules matching, real
  application packet prep, persisted manifests/events, and manual-submit stop.
- 2026-05-14: Cloud loop/CLI tests prove `POST
  /api/cloud/workflows/continue` can create and run a cloud workflow in one
  request, while `ml-job-swarm-cloud-worker` can drain queued runs from a
  configured database.
- 2026-05-14: `uv run pytest tests/test_product_goals.py
  tests/test_live_e2e_smoke_script.py tests/test_source_policy.py -q` -> 18
  passed for quantitative product gates and live-smoke metric output.
- 2026-05-14: `uv run pytest -q` -> 402 passed.
- 2026-06-29: `uv run pytest -q` -> 530 passed, 12 skipped (quantitative gates, cloud operator UI, cloud SLO fixtures, and CI gate subsets).
- 2026-06-29: `uv run pytest tests/test_routes_cloud_ui.py -q` -> cloud operator HTML console routes green.
- 2026-06-29: `uv run pytest tests/test_product_goals.py tests/test_seed_policy_gate.py tests/test_seed_refresh_audit.py tests/test_golden_profile_matching.py tests/test_catalog_quality_gate.py tests/test_error_handling_gates.py tests/test_operator_observability_gate.py -q` -> product-gates CI subset green.
- 2026-06-29: `./scripts/run-cloud-parity-check.sh` -> runtime parity fixture baseline green.
