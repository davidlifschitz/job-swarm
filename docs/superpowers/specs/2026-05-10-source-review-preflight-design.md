# Source Review Preflight Design

## Goal

Show whether a user-submitted source URL is policy-allowed, which adapter type it maps to, and whether it can be refreshed before an admin approves it.

## Why This Matters

The website already lets users add company sources and admins approve them. Without preflight, the queue is opaque: an admin can see a URL but not whether approving it will create a refreshable public source or hit a policy boundary. This slice makes the existing review workflow operational without changing safety rules.

## V1 Scope

- Compute preflight data at render time for review queue rows:
  - source policy mode and reason
  - inferred source type
  - refreshability status against the current public adapter registry
- Render the preflight columns on `/admin/sources`.
- Preserve existing approval behavior:
  - only policy `allowed` sources can be approved
  - blocked sources stay blocked
  - unsupported sources can remain visible without fallback scraping

## Safety Boundaries

- No network fetch happens during preflight.
- No LinkedIn, Indeed, search-proxy, auth-gated, CAPTCHA, cookie, hidden-session, or final-submit behavior is added.
- Preflight must not make manual-link URLs approveable.

## Acceptance Criteria

- Review queue rows show policy, inferred type, and refreshability.
- Public ATS submissions such as Workable are marked ready when the registry supports them.
- Unknown/manual-link submissions are marked not refreshable before approval.
- Existing approval, approve-and-refresh, reject, and blocked-source behavior remains unchanged.

## Review Gates

- `goal-review`: confirm the queue becomes more operational without over-approving unsafe sources.
- `test-quality-review`: confirm tests cover ready and not-refreshable queue preflight states.
