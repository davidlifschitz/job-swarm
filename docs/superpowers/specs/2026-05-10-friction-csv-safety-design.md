# Source Friction CSV Safety Design

Branch: `codex/friction-csv-safety`

## Goal

Make source friction CSV export safe to open in spreadsheet tools.

## Context

Saved jobs CSV now neutralizes formula-like values before writing rows. Source friction CSV still serializes row values directly. Since friction exports can contain URLs, notes, provider messages, or manually reviewed text, it should use the same CSV safety boundary.

## V1 Scope

- Reuse the existing `_csv_safe_row` helper for `/admin/sources/friction.csv`.
- Prefix string cells that start with `=`, `+`, `-`, or `@` after leading whitespace.
- Keep existing secret/resume redaction behavior.
- Do not mutate stored friction event data.

## Out Of Scope

- No new friction filters.
- No admin auth changes.
- No changes to the source friction HTML page.

## Data And Safety

CSV safety is export-only. The database should keep the original review note and friction metadata while the downloaded CSV neutralizes executable spreadsheet cells.

## TDD And Review Gates

- Start with a failing source friction CSV test for formula-like review notes.
- Implement the one-line route serialization change.
- Run focused admin-source tests and the full suite.
- Run goal-review before publishing.
