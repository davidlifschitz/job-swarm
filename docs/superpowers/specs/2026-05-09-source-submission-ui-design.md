# Source Submission UI Design

Status: approved-for-implementation follow-up slice
Date: 2026-05-09
Branch: `codex/source-submission-ui`

## Goal

Give the local user/operator a simple page to submit a company careers URL into the existing source review queue.

## Product Fit

V1 supports user-added company sources in the data layer and admin approval flow. The missing piece is the first UI step: adding a company and careers URL without opening SQLite or writing a script.

## V1 Scope

- Add `/sources/new`.
- Render a form for company name and careers URL.
- POST submissions through `submit_company_source`.
- Redirect to `/admin/sources` after successful submission.
- Preserve source-policy behavior: blocked URLs enter the queue as blocked and record friction; allowed/manual-review URLs enter as pending.
- Link from `/admin/sources`.

## Non-Goals

- No live scraping when submitting.
- No bypass of source policy.
- No auth-gated source setup.
- No CAPTCHA/cookie/browser-profile support.
- No hosted user authentication.

## Safety Rules

- Submission never creates a `job_sources` row directly.
- All suggestions must go through the review queue.
- Blocked sources remain blocked until rejected or manually handled later.

## Tests

- form renders required company/URL fields
- successful allowed source submission creates a pending queue row and redirects to admin
- blocked source submission creates a blocked queue row and friction event
- missing fields return 400
- source admin links to the submission page

## V2 Options

- inline validation hints
- bulk company import UI
- hosted auth when deployed
