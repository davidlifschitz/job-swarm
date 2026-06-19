# Admin Audit Timeline Design

Status: approved-for-implementation follow-up slice
Date: 2026-05-09
Branch: `codex/admin-audit-timeline`

## Goal

Expose local admin actions in a simple audit timeline so source-review and source-health decisions are inspectable without querying SQLite directly.

## Product Fit

The product already records `admin_audit_events` for source review, source disable, and future local admin actions. A visible timeline closes the loop for the user's requested admin/debug view while keeping the system local-first.

## V1 Scope

- Add `/admin/audit`.
- Show actor, action, target type, target id, before state, after state, and timestamp.
- Link from `/admin/sources` to the audit timeline.
- Sanitize event JSON before rendering.
- Keep the page read-only.

## Non-Goals

- No hosted authentication.
- No multi-user permission model.
- No deletion or mutation of audit rows.
- No external log shipping.
- No raw secret, resume, prompt, cookie, token, or browser profile display.

## Safety Rules

- Treat audit JSON as untrusted stored data and sanitize it at render time.
- Reuse the existing sensitive-detail key filter used by friction CSV export.
- Do not include raw private payloads in the page.

## Tests

- admin audit page renders audit rows
- empty audit page renders safely
- sensitive audit fields are excluded
- admin source page links to the audit timeline

## V2 Options

- CSV export for audit rows
- action filters
- hosted admin auth when Cloudflare deployment exists
