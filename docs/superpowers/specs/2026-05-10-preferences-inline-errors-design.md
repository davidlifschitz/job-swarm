# Onboarding Preferences Inline Validation Design

Branch: `claude/fix-website-e2e-Rj73P`

## Goal

When a user submits the onboarding preferences form with one or more required
fields missing, re-render the onboarding page with inline error messages and
the previously typed values preserved, instead of returning a bare
`text/html` 400 page that strands the user with no form to retry.

## Context

V1 done criteria calls for a usable "first-run wizard". Today, POSTing
`/preferences` with missing fields returns
`HTMLResponse("Missing preference: ...", 400)` (`ml_job_swarm/app.py:247`).
The user lands on a blank page with no nav, no form, no link back, and has
to use the browser back button (which will typically discard their typed
values). This is a clear UX dead end on the first page a user sees.

## V1 Scope

- POST `/preferences` with missing required fields re-renders
  `onboarding.html` with status code 400.
- The template renders an `errors` mapping next to each affected field
  (`{"role": "Role is required.", ...}`).
- The template repopulates each preference input with the value the user
  submitted, so they don't lose their work.
- The "missing resume asset" error is surfaced the same way — re-render
  onboarding with a single form-level error message.
- The form action and field names are unchanged.

## Out Of Scope

- No client-side JavaScript validation.
- No styling beyond a `field-error` class and an `aria-invalid` attribute on
  the input.
- No restructuring of the form into a multi-step wizard.
- No per-question option lists; inputs remain free-text.

## Data And Safety

The submitted preference values are short strings (role title, level, etc.)
already destined for storage in the target profile on success. Echoing them
back uses Jinja auto-escape. No new query-string state, no logging of these
values.

## TDD And Review Gates

- Add a route test that POSTs `/preferences` with only `role` and `level`
  filled and asserts the response is 200 OR 400 with the onboarding form
  re-rendered, includes the strings `Role is required` is NOT present (it
  was supplied) but the location/work_mode/company_stage error messages ARE
  present, and the submitted role/level values are reflected in the re-rendered
  form's `value=`.
- Update the existing `test_preferences_missing_disables_matching` to assert
  the new structured error rendering (form re-renders, not a bare error
  page) while still confirming the dashboard remains in onboarding-required
  state.
- Confirm tests fail before implementation.
- Implement the route change and template updates.
- Run focused tests, then full suite.
