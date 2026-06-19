# Source Friction Resolution Design

Branch: `codex/source-friction-resolution`

## Goal

Let local admins mark source friction events reviewed or resolved so scraping pushback can be triaged without retrying, bypassing, or deleting evidence.

## Context

V1 records friction events and now displays a sanitized source-friction log. The next governance gap is event state: every event currently looks equally active forever. Admins need to distinguish new pushback from reviewed events while preserving the log.

## V1 Scope

- Add review metadata to `source_friction_events`: `review_status`, `reviewed_at`, `reviewed_by`, and sanitized `review_note`.
- Default new friction events to `unreviewed`.
- Add `POST /admin/sources/friction/{event_id}/review` for local review updates.
- Accept statuses `reviewed` and `resolved`.
- Store a sanitized, truncated note.
- Record an `admin_audit_events` row for each review update.
- Show review status, reviewer, reviewed time, and note on `/admin/sources/friction`.
- Include review fields in friction CSV export.

## Out Of Scope

- No retry or refresh action.
- No deletion or hiding of friction events.
- No auth/cookie/CAPTCHA bypass.
- No external notification or log shipping.

## Data And Safety

Review notes may be typed by the local operator, so they must be sanitized before storage and display. The same sensitive terms used for audit/friction sanitization apply: no cookies, tokens, API keys, raw resume text, prompts, browser profile data, or source page content.

## TDD And Review Gates

- Start with schema, route, CSV, and page tests.
- Confirm tests fail before implementation.
- Implement schema columns, route, sanitizer, template form, and CSV fields.
- Run focused schema/admin tests, full suite, and browser smoke.
- Run goal-review before publishing.
