# Refresh Suspicious Empty Summary

Date: 2026-05-10
Branch: `codex/suspicious-refresh-summary`

## Goal

Make public refresh summaries show sources that returned no jobs as a first-class
signal, because live seed probing found thousands of real jobs plus many
`suspicious_empty` sources that were only visible in run history/friction rows.

## Scope

- Count `suspicious_empty` results in `RefreshSummary`.
- Include the count in CLI JSON output.
- Include the count in dashboard and admin redirect summaries.
- Render the count in dashboard and admin summary panels.

## Out Of Scope

- New source-specific adapters.
- Changing compliance boundaries.
- Treating suspicious empty as a hard failure.

## Acceptance

- A refresh with an empty adapter reports `suspicious_empty=1`.
- CLI output includes `suspicious_empty`.
- Web refresh redirects include `suspicious_empty`.
- Summary panels show the count so source-adapter backlog is visible.
