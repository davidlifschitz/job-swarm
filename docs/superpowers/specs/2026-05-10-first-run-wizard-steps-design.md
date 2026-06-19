# First-Run Wizard Step Indicator Design

Branch: `claude/fix-website-e2e-Rj73P`

## Goal

Make the onboarding page feel like a "first-run wizard" by adding a visible
3-step progress indicator (Upload resume → Set preferences → See matches) at
the top of the page, with the current step marked active based on whether a
resume has been uploaded yet.

## Context

The V1 done criteria spec explicitly calls out "first-run wizard" under the
User UI column. The onboarding page today is just two stacked `<section
class="panel">` blocks (resume upload + preferences) with no indication that
this is a wizard or which step the user is on. Now that nav is in place
(loop 1) and preferences re-render with errors (loop 3), the missing
ingredient for a true "wizard" feel is the progress indicator.

## V1 Scope

- Add an `<ol class="wizard-steps">` to the top of `onboarding.html` with
  three list items: "Upload resume", "Set preferences", "See matches".
- Mark exactly one step `aria-current="step"`:
  - Step 1 when `resume_asset_id` is unset.
  - Step 2 when `resume_asset_id` is set.
  - Step 3 is always upcoming on this page (the user reaches matches by
    leaving onboarding).
- Add a `data-step-id` attribute (`upload`, `preferences`, `matches`) to
  each list item for testability.

## Out Of Scope

- No CSS theming beyond minimal class names (`wizard-steps`,
  `wizard-step--active`, `wizard-step--upcoming`).
- No mid-flow navigation between steps (the user already moves forward via
  form submits).
- No JavaScript.
- No persistence of "completed" state for repeat visits.

## Data And Safety

The indicator is driven solely by the existing `resume_asset_id` query
parameter that the onboarding route already accepts and sanitises. No new
state.

## TDD And Review Gates

- Add a route test that GET `/onboarding` shows the three steps with step 1
  active (`aria-current="step"`).
- Add a route test that GET `/onboarding?resume_asset_id=42` shows step 2
  active and step 1 marked complete (without `aria-current`).
- Confirm tests fail before implementation.
- Implement the markup in `onboarding.html`.
- Run focused tests, then full suite.
