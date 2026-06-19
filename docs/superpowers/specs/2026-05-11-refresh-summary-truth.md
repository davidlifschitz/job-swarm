# Refresh summary truth design

## Goal

Make source-refresh summaries tell the user what happened against live data:
how many sources were attempted, how many actually succeeded, and how many
failed, blocked, or returned suspicious empty results.

## Problem

The website currently reports `Sources refreshed` for every supported source
attempted by `refresh_due_sources`, including failed, blocked, and suspicious
empty sources. For a real working product, the dashboard and admin pages must not
overstate live data freshness.

A second E2E blocker was found in the no-credentials flow: jobs saved from public
refresh/rules-preview results disappeared from Saved Jobs unless an LLM fit
review row existed. That made the local-only path fail before application packet
prep.

## V1 Design

- Track attempted sources and succeeded sources separately in `RefreshSummary`.
- Keep `sources_refreshed` as a compatibility value for successful refreshes.
- Add `sources_attempted` and `sources_succeeded` to web redirect summaries and
  CLI JSON output.
- Render dashboard/admin summaries as `Sources attempted` and
  `Sources succeeded`.
- Preserve existing failure, blocked, suspicious-empty, skipped, job-seen, and
  job-closed fields.
- Let saved jobs export and saved jobs UI include saved roles that do not yet
  have a fit-review row, with `Not reviewed` fit status and blank score.
- Expose Save/Hide actions on rules-preview and unreviewed dashboard rows so a
  no-credentials user can shortlist live public-refresh jobs in place.
- Preserve active `target_profile_id` in the global Dashboard nav while the user
  is on a profile-scoped page.

## Acceptance

- A failed, blocked, or suspicious-empty source increments attempted but not
  succeeded/refreshed.
- A successful source increments both attempted and succeeded/refreshed.
- Admin and dashboard summary UI no longer labels attempted sources as
  refreshed.
- CLI output exposes attempted and succeeded counts for cron logs.
- Focused route and ingest tests cover the new semantics.
- A public-refresh job can be saved, exported, and prepared as a local manual
  application packet without an LLM fit-review row.
