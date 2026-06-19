# Source Review Workflow Design

Status: approved-for-implementation follow-up slice
Date: 2026-05-09
Branch: `codex/source-review-workflow`

## Goal

Make user-added company career sources first-class: every submitted source is visible to the local admin, can be approved into the catalog or rejected, and leaves an audit trail without weakening the V1 scraping safety boundary.

## User Story

A user can add a company/careers URL that is not in the seed catalog. The system classifies the URL with the same source-policy rules used by ingestion, queues it for review, and the local admin can decide what happens next.

## V1 Scope

- Show pending, approved, rejected, and blocked queued sources on `/admin/sources`.
- Approve only sources that pass `source_policy`.
- Reject pending or blocked queue entries with a local audit event.
- Create or reuse a normalized company row when approving.
- Create or reuse the corresponding `job_sources` row.
- Record `admin_audit_events` for approve and reject actions.
- Keep blocked LinkedIn, Indeed, auth-gated, CAPTCHA, cookie, and hidden-session sources out of `job_sources`.

## Non-Goals

- No live fetch during approval.
- No automatic retry of failed source refreshes.
- No authenticated source setup.
- No Cloudflare admin auth in this slice.
- No browser automation or CAPTCHA handling.

## Data Contract

Existing tables remain the source of truth:

- `company_source_review_queue`: queued user suggestions and review status.
- `companies`: approved companies.
- `job_sources`: approved source URLs eligible for refresh.
- `source_friction_events`: policy blocks and scrape friction.
- `admin_audit_events`: every admin review decision.

Queue status values:

- `pending`: awaiting admin decision.
- `approved`: source was allowed and inserted into `job_sources`.
- `rejected`: admin declined the source.
- `blocked`: source policy rejected it at submission time.

## Admin UI

`/admin/sources` has two sections:

1. Source review queue: company, requested URL, reason, status, submitted timestamp, and approve/reject actions.
2. Source health table: existing refresh health, friction, recommendations, and disable action.

Actions use simple POST forms so they are testable and local-first.

## Safety Rules

- Approval re-runs `classify_source_url`; stale queued data cannot bypass policy.
- Blocked queue entries cannot be approved.
- Rejection never deletes the queue row.
- Audit details include before/after status and target queue/source ids, but no secrets, cookies, resume text, prompts, or browser profile data.
- The workflow is local admin tooling, not a hosted multi-user permission model.

## Tests

Use TDD for the slice:

- catalog helper approves an allowed queued source into `companies` and `job_sources`
- catalog helper rejects a source and records audit
- blocked source approval raises and records no job source
- admin page lists queued sources
- approve route redirects, updates queue, creates source, and audits
- reject route redirects, updates queue, and audits

## V2 Options

- authenticated admin page when the app is deployed
- retry source refresh from a reviewed queue entry
- source quality notes and admin comments
- Cloudflare cron visibility
- browser-agent diagnostics for public pages that push back without requiring auth
