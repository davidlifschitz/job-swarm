# Saved Jobs Export Safety Design

Branch: `codex/saved-jobs-export-isolation`

## Goal

Make saved jobs CSV export explicitly profile-scoped and safe to open in spreadsheet tools.

## Context

Saved jobs export is a local convenience feature for reviewing shortlists outside the dashboard. The export must keep the same privacy boundary as the dashboard: only the active target profile's saved jobs should appear, hidden jobs and other profiles should stay out, and private adjacent data should not leak. CSV adds one more risk: spreadsheet apps can evaluate cells that start with formula prefixes.

## V1 Scope

- Keep requiring `target_profile_id` for `/dashboard/saved.csv`.
- Export only rows whose decision is `saved` for the requested target profile and current profile version.
- Add regression coverage that a different profile's saved row does not appear in the export.
- Neutralize exported string cells that start with spreadsheet formula prefixes after leading whitespace: `=`, `+`, `-`, or `@`.
- Preserve existing CSV headers and unfiltered export behavior.

## Out Of Scope

- No hosted file storage.
- No background export jobs.
- No change to the saved jobs page filtering or sorting.
- No change to user notes storage; sanitization happens only when writing CSV.

## Data And Safety

The export must not include raw resume sections, LLM request payloads, admin audit payloads, or friction details. Spreadsheet formula neutralization should keep values readable while preventing execution when opened by Excel, Numbers, or Google Sheets.

## TDD And Review Gates

- Start with a failing route test for formula-like company/title/notes values and cross-profile saved jobs.
- Implement a narrow CSV value sanitizer used only by the CSV route.
- Run focused route tests and the full suite.
- Run goal-review before publishing.
