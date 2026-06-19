# Saved Application Queue Status

Date: 2026-05-10
Branch: `codex/saved-application-queue`

## Goal

Make saved jobs operate like an application queue by showing whether each saved
job has an application packet and whether manual submission is complete.

## Scope

- Add packet status fields to saved-job rows.
- Render packet/manual-submit status on the saved jobs page.
- Include safe packet status fields in saved CSV export.

## Out Of Scope

- Autonomous job submission.
- Live external application actions.
- Exporting referral contacts or private resume text.

## Acceptance

- Saved jobs with prepared packets show `prepared`.
- Submitted packets show `submitted`.
- Jobs without packets show `not_prepared`.
- CSV includes `packet_status` and `manual_submit_url`, but no private resume
  text or local referral contact data.
