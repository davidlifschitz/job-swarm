# Approve Source Refresh Design

Branch: `codex/approve-source-refresh`

## Goal

Make admin source approval immediately useful by letting the local admin approve
a queued public ATS source and refresh that source in the same web action.

## V1 Scope

- Pending source reviews show an explicit `Approve and refresh` action.
- The action approves the queue item using the same audited review path as
  ordinary approval.
- If the approved source type is supported by the configured adapter registry,
  the app refreshes only that new source.
- If the source type is unsupported, the approval still succeeds and the run
  summary records one skipped source instead of creating a noisy failed run.
- The action redirects to `/admin/runs` with the same refresh summary shape as
  the bulk public-ATS refresh path.

## Safety Boundary

- Public ATS adapters only.
- No unsupported source fetches, cookies, auth, CAPTCHA handling, aggregator
  scraping, hidden browser sessions, or autonomous applications.
- Unsupported sources remain approved for admin visibility but are not fetched
  until an adapter exists.

## Acceptance Criteria

- The source review queue exposes `Approve and refresh` for pending reviews.
- Public ATS approval refreshes exactly the approved source and inserts jobs.
- Unsupported approval reports `sources_skipped=1` with no ingestion run and no
  friction event.
- Existing approve/reject/admin refresh behavior remains intact.
- Full test suite passes.
