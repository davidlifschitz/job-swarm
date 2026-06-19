# Admin Audit Value Redaction Design

Branch: `codex/admin-audit-value-redaction`

## Goal

Harden admin audit and friction exports so sensitive-looking values are redacted even when stored under non-sensitive keys.

## Context

Admin audit and source friction views already remove sensitive JSON keys such as `token`, `cookie`, `raw_resume_text`, and `private_prompt`. A caller can still accidentally store a sensitive string under a harmless key such as `note`, `message`, or `details`. Since these views are intended for local admin review, they should preserve useful safe fields while redacting obvious secret/resume/session text.

## V1 Scope

- Extend the shared detail sanitizer to redact string values that contain sensitive terms.
- Preserve current behavior that removes sensitive keys entirely.
- Keep safe values visible.
- Cover both `/admin/audit` and source friction export paths through focused tests.
- Do not mutate stored audit or friction rows; redaction is presentation/export only.

## Out Of Scope

- No role-based auth for the admin site.
- No new audit event schema.
- No encrypted storage.
- No external secret scanner dependency.

## Data And Safety

Redaction is conservative and local. Strings containing terms such as `token`, `secret`, `cookie`, `session`, `resume`, `prompt`, `auth`, `browser_profile`, or `key` should render as `[redacted]`.

## TDD And Review Gates

- Start with failing route tests for audit page and friction CSV value redaction.
- Implement one shared sanitizer change.
- Run focused admin-source tests and the full suite.
- Run goal-review before publishing.
