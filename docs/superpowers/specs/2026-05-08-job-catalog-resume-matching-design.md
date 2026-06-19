# Job Catalog and Resume Matching Design

Status: approved design draft for implementation planning
Date: 2026-05-08
Branch: `codex/design-spec-assets`
Legacy system: `Legacy/`

## Goal

Rebuild `ml-job-swarm` from first principles as a local-first job discovery product: a daily refreshed catalog of curated company jobs, resume-driven preferences, rules-first filtering, OpenRouter fit review, grouped company results, clickable resume assistance, and local source-health admin tools.

## Non-Goals

- No application workflow in V1.
- No final submit automation.
- No outreach, referrals, CRM, reminders, or notification workflows in V1.
- No LinkedIn or Indeed ingestion in V1.
- No auth-gated, cookie-based, CAPTCHA bypass, or hidden-session scraping in V1.
- No full resume designer in V1.
- No Cloudflare dependency for V1.

## Supporting Visuals

- `design-specs/2026-05-08-v1-ui-mockup.png`
- `design-specs/2026-05-08-scoring-ingestion-flow.png`
- `design-specs/2026-05-08-admin-source-health-mockup.png`
- `design-specs/2026-05-08-v1-done-criteria.png`
- `design-specs/2026-05-08-first-principles-scratch-spec.png`

## V1 Product Shape

The product has two loops.

First, a daily catalog refresh keeps jobs fresh:

```text
curated companies -> source policy -> public careers/ATS fetch -> snapshots -> canonical jobs
```

Second, a user profile filters and reviews those jobs:

```text
resume upload -> parse + keywords -> preferences -> rules filter -> LLM fit gate -> grouped company results
```

The catalog exists before the user starts onboarding. User preferences filter the latest stored catalog; they do not trigger live scraping as a required path.

## V1 and V2 Boundary

V1 includes:

- roughly 50 curated tech, AI, quant, fintech, and developer-tool companies
- user-added company sources
- daily local refresh command or cron-friendly entrypoint
- PDF/DOCX resume upload
- local resume parsing
- consented vision fallback for low-confidence PDFs
- section-aware resume workspace
- fixed multiple-choice preferences
- rules-first job filtering
- OpenRouter fit gate with scores and labels
- grouped company results
- local admin/source-health page
- strict TDD and test-quality gates

V2 candidates:

- larger 150-company and 500-company catalogs
- Cloudflare scheduled refresh/deployment
- authenticated or user-mediated source integrations, only with explicit consent and clear legal footing
- full resume designer and tailored resume exports
- application preparation and manual-submit workflow
- parallel Hermes/browser-use workflow QA against the running app

CAPTCHA bypass remains out of scope. Blocked sources fall back to manual link/import or admin review.

## Architecture

Use a boring local stack:

- Python package for domain logic
- SQLite as the source of truth
- a lightweight web app/API for the dashboard and admin page
- OpenRouter client isolated behind typed contracts
- browser/public-page ingestion isolated behind source policy and adapters

Suggested modules:

- `ml_job_swarm/store.py`
- `ml_job_swarm/models.py`
- `ml_job_swarm/source_policy.py`
- `ml_job_swarm/catalog.py`
- `ml_job_swarm/ingest.py`
- `ml_job_swarm/resume_extract.py`
- `ml_job_swarm/profile.py`
- `ml_job_swarm/filtering.py`
- `ml_job_swarm/llm.py`
- `ml_job_swarm/app.py`

Each module should expose small contracts and be testable without live network or model calls.

## Company Catalog

V1 starts with a small high-quality seed list, not broad generated coverage.

Company categories:

- AI labs
- AI infrastructure
- big tech
- model/application startups
- quant trading
- hedge funds
- fintech
- developer tools

Company source fields:

- company name
- aliases
- domain tags
- company stage
- careers URL
- ATS type, if known
- source policy mode
- refresh cadence
- last success timestamp
- failure count
- review status

User-added company flow:

```text
company + careers URL -> source policy check -> review queue -> next daily refresh
```

Optional manual "refresh this source" can be added later, but the V1 design does not require session-time scraping.

## Daily Refresh

V1 refresh is a daily scheduled job or cron-friendly command.

Behavior:

- records every `ingestion_run`
- stores raw job snapshots
- updates canonical active jobs
- preserves stale-but-valid results if a refresh fails
- writes source friction events for blocked or failing sources
- treats suspicious empty results conservatively before closing jobs

Cloudflare scheduling is a later deployment setup, not a V1 product dependency.

## Source Policy

Allowed:

- public employer career pages
- public ATS job boards
- user-entered public company career URLs

Blocked in V1:

- LinkedIn
- Indeed
- auth-gated pages
- cookie/session scraping
- CAPTCHA bypass
- hidden browser sessions
- scraped SERP proxies

Failure categories:

- `policy_blocked`
- `source_unreachable`
- `ats_unknown`
- `layout_changed`
- `empty_suspicious`
- `rate_limited`
- `captcha_or_login`
- `blocked_response`
- `timeout`
- `manual_review_needed`

Fail closed. Do not hammer hostile sources.

## Friction Log and Admin Page

Every blocked, hostile, or suspicious refresh writes a `source_friction_events` row.

V1 includes a local admin/debug page with:

- source list by company
- last refresh time
- active job count
- latest status
- failure count
- latest friction event
- retry recommendation
- disabled/quarantined flag

Admin actions:

- mark source reviewed
- disable source
- enable source
- safe retry, if implemented
- export friction log as CSV

Admin actions write `admin_audit_events`.

No cookies, secrets, raw resumes, raw private prompt logs, or browser profiles may appear in logs.

## Resume Intake and Extraction

V1 supports PDF and DOCX upload.

Extraction order:

1. local deterministic parser
2. parser-confidence check
3. user consent
4. vision fallback through OpenRouter only when confidence is low
5. user review and confirmation

DOCX parsing:

- use local document parsing
- extract paragraphs, headings, bullets, and tables
- preserve rough order

PDF parsing:

- use local text/layout extraction first
- retain page number and layout blocks when possible
- detect low-confidence output

Low confidence signals:

- text length too low
- no recognizable sections
- garbled or single-character tokens
- suspicious reading order
- image-heavy or scanned pages

Vision fallback:

- render pages locally to images
- ask explicit consent before sending any resume page image or resume-derived content to OpenRouter
- request strict JSON: sections, keywords, confidence, warnings
- store metadata, not raw private prompt logs

User can paste resume text if parsing fails or consent is not granted.

## Resume Workspace

V1 is a section-aware resume workspace, not a full designer.

Capabilities:

- render detected sections
- click sections such as `Summary`, `Experience`, `Skills`, `Projects`, and `Education`
- ask OpenRouter for rewrite suggestions for only the selected section
- accept, edit, or reject suggestions
- feed confirmed resume profile into matching

V2 adds layout, typography, tailored variants, and export.

## Preferences

The first-run wizard asks fixed multiple-choice questions:

- role
- level
- location
- work mode
- company stage

The LLM may tailor wording or options from the confirmed resume profile, but the question schema remains fixed in V1.

Preferences are versioned. Changing preferences increments the target profile version and invalidates dashboard use of older fit reviews.

## Rules Filter

Rules are the cheap deterministic gate before LLM review.

Outcomes:

- `pass`
- `soft_pass`
- `reject`

Rules check:

- role family
- level/seniority
- location
- work mode
- company stage
- required skill overlap
- explicit user exclusions

Rules must be conservative. If fit is unclear, return `soft_pass` and send to the LLM fit gate. Reject only obvious non-matches.

## OpenRouter Contracts

OpenRouter is used behind strict schemas only.

V1 purposes:

- profile draft
- questionnaire wording/options
- selected resume section rewrite
- job fit gate
- low-confidence resume vision fallback

Every request records metadata in `llm_requests`:

- purpose
- provider
- model
- schema name
- schema version
- input reference
- status
- error type

Do not store raw private prompt logs.

Private resume content or resume images require explicit user consent before leaving the local machine.

### Job Fit Gate Output

```json
{
  "fit_score": 86,
  "label": "Strong fit",
  "reasons": ["ML infrastructure experience aligns"],
  "risks": ["Kubernetes depth unclear"],
  "must_have_mismatches": [],
  "recommendation": "show"
}
```

Labels:

- `Strong fit`
- `Possible fit`
- `Mismatch risk`
- `Filtered out`

Main results show strong and possible fits. Mismatch risks are hidden by default under each company. Filtered-out jobs are stored but not shown in normal V1 UI.

## Data Model

SQLite is the source of truth.

Catalog:

```text
companies
job_sources
company_source_review_queue
ingestion_runs
source_friction_events
admin_audit_events
job_snapshots
jobs
```

Resume/profile:

```text
resume_assets
resume_parse_runs
resume_sections
resume_keywords
target_profiles
preference_answers
resume_rewrite_suggestions
```

Matching:

```text
rules_filter_results
fit_reviews
llm_requests
```

Key fields:

- `resume_parse_runs.parser_confidence`
- `resume_parse_runs.needs_vision_fallback`
- `resume_parse_runs.vision_fallback_status`
- `resume_parse_runs.vision_fallback_consented_at`
- `target_profiles.version`
- `fit_reviews.fit_score`
- `fit_reviews.label`
- `fit_reviews.reasons_json`
- `fit_reviews.risks_json`
- `fit_reviews.recommendation`
- `fit_reviews.target_profile_version`
- `fit_reviews.llm_request_id`

Raw snapshots are append-only. `jobs` is the current canonical view.

Indexes:

- active jobs by company
- source runs by source/time
- fit reviews by profile version/job
- FTS5 over job title, description, and requirements
- content hash for dedupe

## User UI

V1 uses a first-run wizard, then a persistent dashboard.

First-run wizard:

- upload resume
- parse and review sections/keywords
- consent to fallback or OpenRouter resume processing when needed
- answer fixed preferences
- land on grouped results

Dashboard:

- left panel: profile, resume keywords, preferences, catalog timestamp
- center: grouped company table
- right panel: selected job or resume section assistant

Company row:

- company name
- visible match count
- top score
- latest refresh timestamp
- mismatch-risk count
- optional remote count or hiring trend when cheaply available

Jobs expand under companies. Mismatch-risk jobs live under a collapsed section per company.

## Admin UI

V1 includes a local-only admin/debug page.

It shows:

- company/source health
- last refresh
- active jobs
- status
- failure count
- latest friction event
- recommendation
- safe admin actions

If hosted later, it requires authentication before exposure.

## Review Gates

Specs, plans, and major implementation slices must use:

- `goal-review`: checks alignment with the active thread/product goal
- `test-quality-review`: checks whether tests genuinely prove product behavior

Implementation should not proceed from spec to plan unless `goal-review` passes. Implementation should not be marked complete unless `test-quality-review` finds no blocking gaps.

## Spec-Driven TDD

Implementation is test-first where practical.

Required test layers:

- unit tests for source policy, parser confidence, rules filtering, LLM schemas, dedupe, and scoring labels
- integration tests for catalog refresh, snapshots, canonical jobs, target profiles, fit reviews, and source friction logs
- API/route tests for resume upload, preferences, grouped results, and admin source health
- UI smoke tests for onboarding, grouped table expansion, hidden mismatch risks, clickable resume sections, and admin page
- contract tests for OpenRouter request/response schemas with mocked providers
- regression fixtures for tricky resumes, low-confidence PDFs, seniority mismatches, and blocked sources

External services are mocked in tests. Tests still assert schemas, metadata, persistence, and failure states.

V2 QA idea:

- run parallel Hermes agents with browser-use against the local app
- assign independent workflows to each agent
- compare failures and screenshots
- use after deterministic tests are stable

## Implementation Phases

1. Project skeleton and SQLite schema.
2. Company catalog and daily ingestion.
3. Resume upload, extraction, parser confidence, and fallback contracts.
4. Preferences and target profiles.
5. Rules filter and OpenRouter fit gate.
6. Main dashboard.
7. Admin/source-health page.
8. Test hardening and fixtures.

Each phase needs tests before or alongside production code and must keep live network/model calls mocked by default.

## Acceptance Criteria

V1 is done when:

- roughly 50 curated companies exist with career sources and tags
- daily refresh stores snapshots and canonical jobs
- user-added company sources enter review/refresh flow
- source friction events are recorded
- local admin page shows source health
- PDF/DOCX resume upload works
- local parsing extracts sections and keywords
- low-confidence PDF parse triggers consented vision fallback
- clickable resume sections support LLM rewrite suggestions
- preferences are collected and versioned
- rules filter runs before LLM fit review
- LLM fit review returns 0-100 score, label, reasons, and risks
- mismatch-risk jobs are hidden under each company by default
- grouped company dashboard works
- no raw resume/private prompt logs/cookies/secrets are logged
- LinkedIn/Indeed/auth/CAPTCHA/hidden-session scraping is blocked in V1
- relevant unit, integration, contract, route, and smoke tests pass

## Open Questions for Implementation Planning

- Exact initial 50-company seed list.
- Preferred local web stack.
- Exact OpenRouter model choices for text and vision fallback.
- Whether manual source retry ships in V1 or only admin status/review.
- How much UI polish belongs in the first implementation slice.
