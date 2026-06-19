# Admin Source Recovery Design

Branch: `codex/admin-source-recovery`

## Goal

Let a local admin re-enable a disabled company job source from the source-health page while recording a sanitized audit event.

## Context

V1 already includes source-health visibility, source disable, source review, friction logging, and an audit timeline. The main first-principles spec also lists "enable source" as an admin action. Today a source can be disabled, but the UI has no recovery path, which makes temporary quarantine effectively permanent unless the user edits SQLite directly.

## V1 Scope

- Add a local-only `POST /admin/sources/{source_id}/enable` route.
- Clear `job_sources.disabled_at` for existing sources.
- Return `404` when the source does not exist.
- Record an `admin_audit_events` row with action `enable`, target type `job_source`, and before/after `disabled_at` metadata only.
- Show `Enable` instead of `Disable` for disabled sources on `/admin/sources`.
- Keep enabled sources using the existing `Disable` action.

## Out Of Scope

- No immediate scraping or refresh when a source is enabled.
- No Cloudflare scheduling changes.
- No hosted admin authentication.
- No support for restricted/auth/CAPTCHA sources beyond the existing source policy.

## Data And Safety

The route mutates only `job_sources.disabled_at` and writes audit metadata. It must not log raw resume text, cookies, tokens, prompts, or source page contents. Existing Jinja escaping and audit sanitization handle display.

## TDD And Review Gates

- Start with route tests for enabling a disabled source, `404` on missing source, and conditional admin buttons.
- Run the focused admin-source route tests before implementation and confirm the new tests fail.
- Implement the smallest route/template change.
- Run focused tests, then the full suite.
- Browser-smoke `/admin/sources` with one disabled source and verify the `Enable` action is visible.
- Run goal-review before publishing.
