# Source health labels design

## Goal

Make `/admin/sources` distinguish adapter refreshability from live source
health so operators do not read `Ready` as proof that a source is healthy.

## Problem

The current primary badge says `Ready` whenever a source has a supported adapter.
That is true for refreshability, but not for current health: the source may be
unchecked, failing, suspicious-empty, or recovered.

## V1 Design

- Keep `adapter_status` for whether the Refresh action can run.
- Add a separate health badge:
  - `Unchecked` when supported but never refreshed.
  - `Healthy` when checked successfully and no current friction remains.
  - `Needs review` when current friction exists.
  - `No adapter` for unsupported sources.
  - `Disabled` for disabled sources.
- Keep friction and recommendation notes visible under the health badges.

## Acceptance

- Never-checked supported sources render `Adapter ready` plus `Unchecked`.
- Successfully checked sources with active jobs render `Healthy`.
- Sources with current friction render `Needs review`.
- Unsupported and disabled sources remain explicit.
- Route tests cover each label.
