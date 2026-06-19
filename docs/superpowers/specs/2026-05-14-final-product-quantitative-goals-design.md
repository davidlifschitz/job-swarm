# Final Product Quantitative Goals Design

Created: 2026-05-14

## Goal

Define the measurable final-product bar for `ml-job-swarm`: a local-first,
compliance-first job search and application-prep product that reliably turns
approved public employer/ATS sources into reviewed opportunities, local referral
context, and manually submitted application packets.

The product is done when the metrics below are true in repeatable tests, live
operator smoke runs, and seeded fixture audits. This is not a release checklist
for one slice; it is the quantitative target state every implementation plan
should move toward.

## Product Behavior Contract

- The system must prefer public employer and ATS sources, classify unsupported
  or disallowed sources explicitly, and fail closed when source policy is
  uncertain.
- The system must never autonomously submit applications, send outreach, scrape
  blocked job boards through proxies, or hide those choices behind other search
  providers.
- The system must make the next operator action obvious: refresh a source,
  review a match, save a job, add a local referral contact, prepare a packet, or
  manually mark the packet submitted.
- The system must distinguish deterministic local behavior from optional
  consent-gated LLM behavior in both UI copy and stored state.
- The system must preserve privacy: resumes, notes, referral contacts, and
  application packets stay local unless the operator takes an explicit export or
  external-site action.

## Quantitative Goals

| Area | Final Product Target | Measurement |
| --- | --- | --- |
| First-run setup | A new local operator can reach a dashboard with seeded public sources and resume/profile guidance in <= 10 minutes from a clean clone. | `uv run --with uvicorn --with playwright python scripts/live_e2e_smoke.py` plus documented first-run checklist. |
| Source policy | 100% of configured seed sources are classified as `supported`, `unsupported`, `blocked`, or `needs_review`; 0 ambiguous sources can refresh silently. | Source-policy unit tests plus seeded-source audit. |
| Public source refresh | >= 90% of supported public ATS/employer sources refresh successfully in the nightly seed audit; every failure has a visible reason. | Refresh run summary: attempted, succeeded, failed by reason, and last-success timestamp. |
| Catalog quality | Duplicate canonical job rows stay below 2%; closed or missing public jobs are hidden from default review within 48 hours of a successful refresh. | Catalog fixture tests and live source refresh audit. |
| Job matching | For seeded profile fixtures, >= 80% of top-20 ranked jobs match the expected target family and seniority band; 100% include visible match reasons. | Golden profile/job fixture tests. |
| LLM review boundary | 0 LLM fit reviews run without explicit operator consent and configured runtime credentials; missing consent returns a visible non-2xx result. | Route tests with fake clients and no-client/ no-consent cases. |
| Saved-job workflow | Saving, unsaving, filtering, and CSV export preserve the exact visible filtered set with 100% deterministic status labels. | Dashboard route tests and CSV snapshot assertions. |
| Referral workspace | For local contacts, company matching has >= 95% precision on seeded aliases and subsidiaries; 0 referral suggestions trigger outreach. | Store tests, route tests, and alias fixture tests. |
| Application packets | >= 95% of eligible saved jobs can prepare a packet containing job URL, company, title, resume asset status, match summary, referral context, and manual-submit checklist. | Packet route tests plus live smoke packet assertion. |
| Manual submission | 0 code paths submit an application externally; 100% submitted statuses require an operator action in the local UI or CLI. | Source scan guard, route tests, and packet status transition tests. |
| UI responsiveness | Dashboard, job detail, saved jobs, and admin sources render p95 <= 1 second with 500 local jobs and 50 sources on a developer laptop. | Local performance smoke test with seeded data. |
| Operator observability | 100% of refresh, review, save, export, packet, and status-transition actions have timestamped local audit entries with redacted sensitive values. | Audit store tests and admin route tests. |
| Reliability gate | Focused tests for changed behavior pass, full `uv run pytest -q` passes, and live smoke reports `browser_e2e_ok` before publish. | CI/local command evidence captured in the implementation plan. |
| Error handling | 100% of expected operator-facing failures render a next action and do not leave partial hidden state. | Route tests for source failure, no resume, no profile, no consent, and no adapter cases. |

## TDD Setup

Every implementation slice that moves these goals must start with a failing
behavior test. The test name should describe the measurable product behavior,
not the helper function that happens to implement it.

Recommended first red tests:

1. `test_seed_sources_have_explicit_policy_classification`
   - Fails until every configured seed source has a deterministic source-policy
     outcome and no ambiguous refresh path.
2. `test_live_smoke_reports_quantitative_product_metrics`
   - Fails until the live smoke result includes first-run, source, catalog, and
     packet metrics with threshold-ready names.
3. `test_dashboard_renders_next_action_for_each_empty_or_failed_state`
   - Fails until onboarding, dashboard, job detail, and admin sources always
     show the next operator action.
4. `test_application_packet_requires_manual_submit_boundary`
   - Fails until packet preparation and submitted status transitions prove no
     external submit path exists.
5. `test_local_referrals_match_company_aliases_without_outreach`
   - Fails until local referral suggestions are precise on alias fixtures and
     cannot initiate outbound contact.
6. `test_catalog_quality_thresholds_hold_for_seeded_refresh`
   - Fails until duplicate rate, stale closed-job handling, and visible failure
     reasons are measured from seeded fixtures.

Green code for each slice should be the narrowest implementation that makes its
test pass. Refactors are allowed only after the focused test and current
regression suite stay green.

## Done Criteria

- A final-product metric is not accepted unless it has an automated test or a
  documented live-smoke measurement path.
- Any product behavior that touches external systems must include a compliance
  boundary test before implementation.
- Any UI workflow marked complete must prove both success and empty/failure
  states with route or browser-level assertions.
- Any LLM-assisted behavior must prove consent, no-client, and successful fake
  client paths before live runtime wiring.
- Any export or audit behavior must prove redaction and exact record selection.

## Implementation Evidence

- `tests/test_product_goals.py` covers the six recommended red tests from this
  spec as executable metric gates.
- `ml_job_swarm/product_goals.py` implements seed-source classification,
  threshold-ready live-smoke metrics, next-action coverage, manual-submit
  boundary scanning, local referral alias precision, and catalog-quality
  measurements.
- `scripts/live_e2e_smoke.py` now includes a `product_metrics` object in its
  JSON output so operator smoke runs report the quantitative final-product bar.
- 2026-05-14 verification: focused product/source/smoke tests passed and
  `uv run pytest -q` reported 402 passing tests.

## Out Of Scope

- Live autonomous application submission.
- Automated referral outreach.
- Unauthorized scraping or proxy scraping of blocked job boards.
- Paid hosted multi-user SaaS behavior.
- Replacing local-first storage with a remote sync service.

## Review Gates

- `goal-review`: confirm the metric advances the final local-first product, not
  just an internal implementation preference.
- `test-quality-review`: confirm tests prove real user behavior, edge cases,
  privacy boundaries, and compliance boundaries.
- `verification-before-completion`: confirm focused tests, full suite, and live
  smoke evidence before marking any metric achieved.
