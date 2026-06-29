# Plan Index

Read this before starting new implementation loops. Historical plans stay in
this directory, but this index tracks the currently relevant V1 product slices.

| Status | Plan | Notes |
| --- | --- | --- |
| Done | `2026-05-11-application-packet-integrity.md` | Submitted packet status is preserved and accepted resume rewrites are carried into packet artifacts. |
| Done | `2026-05-11-live-e2e-smoke-operator-logs.md` | Live smoke writes Uvicorn logs and progress artifacts for operator debugging. |
| Done | `2026-05-11-refresh-summary-truth.md` | Source refresh attempted vs succeeded truth plus no-LLM saved-job E2E path. |
| Done | `2026-05-11-live-e2e-smoke-script.md` | Durable local live browser smoke command for the no-credentials E2E path. |
| Done | `2026-05-11-source-health-recovery.md` | Current source health suppresses stale friction after later successful refresh while preserving friction logs. |
| Done | `2026-05-11-source-health-labels.md` | Admin source rows separate adapter refreshability from live health labels. |
| Done | `2026-05-11-product-grade-first-run.md` | First-run website shell, deployment status, onboarding/admin polish. |
| Done | `2026-05-10-web-refresh-public-ats.md` | Dashboard/admin public source refresh route. |
| Done | `2026-05-10-web-job-review.md` | Consent-gated fit review from the dashboard. |
| Done | `2026-05-10-saved-job-shortlist.md` | Saved jobs page. |
| Done | `2026-05-10-application-prep-workspace.md` | Local packet prep and manual-submit status. |
| Done | `2026-05-10-source-friction-log.md` | Source friction log and admin visibility. |
| Done | `2026-05-08-job-catalog-resume-matching.md` | Original V1 foundation plan, reconciled as complete. |
| Done | `2026-06-29-job-swarm-completion-orchestration.md` | Quantitative product gates: `product_goals.py`, seed-policy gate, golden-profile matching, catalog quality, offline seed refresh audit, and hosted env template (`.env.hosted.example`). |
| Done | `2026-06-29-job-swarm-completion-orchestration.md` | Cloud operator UI: dashboard active-run card, `/cloud/runs` list/detail, cancel/start forms, and auth scoping (`tests/test_routes_cloud_ui.py`). |
| Done | `2026-06-29-job-swarm-completion-orchestration.md` | Cloud SLO code: structured cloud logging, runtime parity fixtures, load-capacity fixture, health probe script, and error/observability gate tests. |
| Done | `2026-06-29-job-swarm-completion-orchestration.md` | CI workflows: `product-gates` job in `ci.yml` and `cloud-parity.yml` on PR/push (nightly live seed audit workflow pending W4-T2). |

When a new PR finishes a slice, update this index and
`docs/superpowers/e2e-product-readiness.md` in the same branch.
