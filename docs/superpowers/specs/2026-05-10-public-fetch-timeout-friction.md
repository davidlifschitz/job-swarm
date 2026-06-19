# Public Fetch Timeout Friction

Date: 2026-05-10
Branch: `codex/public-fetch-timeout-friction`

## Goal

Keep source friction diagnostics accurate when public ATS/careers requests time
out after retry.

## Problem

The public fetchers retry transient timeouts, but if all attempts time out the
wrappers report the failure as `blocked_response`. That makes cron/admin output
look like source pushback even when the immediate cause is network or provider
latency.

## Scope

- Preserve existing bounded retry behavior.
- Classify persistent timeout-shaped failures as `timeout`.
- Keep HTTP errors classified as `blocked_response` with status codes.

## Out Of Scope

- Changing retry count or timeout length.
- Treating timeouts as successful refreshes.
- Adding browser automation, auth, CAPTCHA, cookies, or hidden sessions.

## Acceptance

- Persistent timeout in JSON, text, and POST fetch paths raises
  `RefreshError(..., event_type="timeout")`.
- HTTP 403 still raises `blocked_response` with `status_code=403`.
- Existing transient timeout retry tests continue passing.
