# Dashboard Filter Return Path Design

Branch: `codex/dashboard-filter-return-to`

## Goal

Preserve the active dashboard decision filter after save, hide, or clear actions.

## Context

Dashboard decision filters were added as query-param views. The decision POST route already accepts a safe `return_to` path, but dashboard forms do not submit one, so actions fall back to `/dashboard?target_profile_id=<id>` and drop `decision_filter`.

## V1 Scope

- Add `return_to` hidden inputs to dashboard job decision forms.
- Preserve the current dashboard path and query string, including `target_profile_id` and `decision_filter`.
- Cover visible-row save/hide/clear forms and hidden-section clear forms.
- Do not change the decision route semantics.

## Out Of Scope

- No client-side routing.
- No changes to job detail page return behavior.
- No new decision filters or decision states.

## Data And Safety

This is navigation-only. It must not alter decision validation, target profile scoping, or stored notes.

## TDD And Review Gates

- Start with a failing dashboard template route test that asserts filtered dashboard forms include the active `return_to`.
- Implement template-only hidden inputs.
- Run focused route tests and the full suite.
- Run goal-review before publishing.
