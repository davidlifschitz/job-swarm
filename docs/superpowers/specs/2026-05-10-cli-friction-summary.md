# CLI Friction Summary

Date: 2026-05-10
Branch: `codex/cli-friction-summary`

## Goal

Make the daily refresh command's JSON output useful enough to diagnose source
friction from cron logs.

## Problem

`ml-job-swarm refresh` records detailed source friction in SQLite, but the CLI
summary only reports aggregate counts such as `failures` and
`suspicious_empty`. A cron operator can see that something failed, but cannot
tell whether the current run hit blocked responses, suspicious empty pages, or
specific HTTP status codes without opening the admin UI or database.

## Scope

- Add `friction_events` to the refresh JSON summary.
- Add `friction_status_codes` to the refresh JSON summary.
- Count only friction rows created by the current command invocation.

## Out Of Scope

- Changing refresh behavior, source policy, or cron exit codes.
- Exporting private data, request bodies, cookies, or credentials.
- Live browser scraping or CAPTCHA/auth handling.

## Acceptance

- Suspicious-empty refreshes report `friction_events.empty_suspicious`.
- Blocked public fetches report `friction_events.blocked_response`.
- HTTP failures with known status codes report `friction_status_codes`.
- Existing success summaries still include empty friction summary objects.
