# Source health recovery design

## Goal

Make admin source health reflect current live refresh state instead of showing
stale friction after a source successfully recovers.

## Problem

`/admin/sources` currently displays the latest friction event for a source even
when a later successful refresh has marked the source checked and inserted live
jobs. That makes a recovered source look broken and undermines operator trust in
the live catalog.

## V1 Design

- Keep `source_friction_events` append-only for audit and friction review.
- In source health rows, treat the latest friction event as current only when it
  is not older than the source's successful `last_checked_at`.
- If `last_checked_at` is newer than the latest friction event and the source
  has active jobs, render source health as currently healthy:
  - `Friction: none`
  - `Recommendation: healthy`
- Preserve the historical event in `/admin/sources/friction` and CSV exports.

## Acceptance

- A source with only friction still shows the event and recommendation.
- A source with later successful live refresh no longer shows stale friction in
  the source health table.
- The friction log still contains the older friction event.
- Focused admin route tests prove both states.
