# Vision Fallback Decline Design

Branch: `claude/fix-website-e2e-Rj73P`

## Goal

Give the user an explicit, recorded way to decline the vision-fallback
prompt and proceed with whatever the local parser already extracted. Today
the only visible action in the "Vision fallback" panel is a single "Use
vision fallback" button; declining is implicit (you have to know to ignore
the panel and scroll down to the preferences form), and the user's choice
is never recorded in the parse run.

## Context

V1 done criteria explicitly requires "vision fallback w/ consent". Consent
is binary — there must be a way to NOT consent without leaving the wizard.
The schema already accommodates this: `resume_parse_runs.vision_fallback_status`
is a free-form TEXT column currently set to `not_needed`, `pending_consent`,
or `consented`. Adding a `declined` value records the user's choice without
any schema change. After declining, the wizard should hide the
vision-fallback panel and let the user complete preferences with the
partial parse.

## V1 Scope

- Add a POST route `/resume/decline-vision-fallback` that:
  1. Loads the latest parse run for the given `resume_asset_id` whose
     `vision_fallback_status = 'pending_consent'`.
  2. Updates that row to `vision_fallback_status = 'declined'`.
  3. Redirects (303) to `/onboarding?resume_asset_id={id}` (no
     `vision_fallback=needed`).
  4. Returns 400 if no `resume_asset_id` is provided or no pending parse
     run is found, mirroring the existing `/resume/vision-fallback` route.
- Add a "Skip and use what we parsed" button to the vision-fallback panel
  in `onboarding.html` that submits to the new route. Place it next to
  the existing "Use vision fallback" button.
- Update the panel copy to clarify both options exist.

## Out Of Scope

- No changes to how a declined parse is matched downstream (whatever
  sections/keywords were captured remain in the DB and feed matching just
  like a normal parse).
- No new column on `resume_parse_runs`.
- No JavaScript.
- No audit-log entry separate from the existing `vision_fallback_status`
  field.

## Data And Safety

The decline route reads the parse-run row keyed on `resume_asset_id` with
`status='needs_vision_fallback'` and `vision_fallback_status='pending_consent'`
to scope the update to the active prompt. It updates a single column. No
private resume content is read, written, or logged. Output is the
existing onboarding redirect.

## TDD And Review Gates

- Add a route test that uploads a low-confidence resume (existing helper
  pattern), POSTs to `/resume/decline-vision-fallback` with the
  `resume_asset_id`, asserts a 303 redirect to `/onboarding?resume_asset_id=...`
  with NO `vision_fallback=needed`, and asserts the parse run row now has
  `vision_fallback_status='declined'`.
- Add a route test asserting the onboarding template (when
  `vision_fallback=needed`) renders both the "Use vision fallback" button
  and a "Skip and use what we parsed" button pointing at
  `/resume/decline-vision-fallback`.
- Add a route test asserting POSTing the decline route with no pending
  parse run returns 400.
- Confirm tests fail before implementation.
- Implement the route, the template button, and copy update.
- Run focused tests, then the full suite.
