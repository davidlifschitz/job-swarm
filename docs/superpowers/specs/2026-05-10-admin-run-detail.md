# Admin Run Detail

Date: 2026-05-10
Branch: `codex/admin-run-detail`

## Goal

Let admins drill into a public-source refresh run and see which sources and
jobs made the run succeed, fail, or return suspicious-empty results.

## Scope

- Add `/admin/runs/{run_id}`.
- Link run history rows to the detail page.
- Show sanitized run metadata and errors.
- Show sanitized source friction events tied to the run.
- Show job snapshots captured during the run.

## Out Of Scope

- New source-specific adapters.
- Editing or retrying sources from the detail page.
- Showing raw private prompts, raw resume text, cookies, tokens, or browser
  profiles.

## Acceptance

- Run history links to individual run detail pages.
- Missing run IDs return 404.
- Run detail shows run counts, friction event diagnostics, and captured job
  snapshots.
- Sensitive values in errors or friction details are redacted.
