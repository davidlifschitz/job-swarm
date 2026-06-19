# Source Friction Log Design

Branch: `codex/source-friction-log`

## Goal

Expose source friction events in a local admin page so scraping pushback, policy blocks, auth walls, CAPTCHA indicators, and source failures can be reviewed without opening SQLite or CSV.

## Context

V1 already records `source_friction_events` and exports a sanitized friction CSV. The admin source-health table shows only the latest event per source. A dedicated log page makes the event history visible while preserving the compliance boundary.

## V1 Scope

- Add `GET /admin/sources/friction`.
- Render sanitized friction events with company, source URL, event type, status code, safe details, and created time.
- Link to the friction page from `/admin/sources`.
- Keep `/admin/sources/friction.csv` working.
- Reuse existing sensitive-detail sanitization.

## Out Of Scope

- No event deletion or mutation.
- No retry/refresh action.
- No auth/cookie/CAPTCHA bypass.
- No external log shipping.

## Data And Safety

Details must be sanitized exactly like the CSV export. The page must not render cookies, tokens, API keys, raw resume text, raw prompts, or browser profile data.

## TDD And Review Gates

- Start with route tests for empty state, populated sanitized rows, source-page link, and CSV compatibility.
- Confirm tests fail before implementation.
- Add route and template.
- Run focused tests, full suite, and browser smoke.
- Run goal-review before publishing.
