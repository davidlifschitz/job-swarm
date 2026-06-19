# Decision Flash Feedback Design

Branch: `claude/fix-website-e2e-Rj73P`

## Goal

After a user saves, hides, or clears a job decision, render a brief
confirmation banner on the next page so the user has visible proof their
click worked.

## Context

Today, POST `/jobs/{id}/decision` (`ml_job_swarm/app.py:365`) calls
`record_job_decision` or `clear_job_decision`, then 303-redirects back to
the page the user came from (`return_to` if safe, else the dashboard). The
next page renders identically with the new state, but there is no banner,
toast, or status line confirming the action. Users on the dashboard, saved
jobs page, or job detail page are left to scan the row to figure out
whether the click registered.

V1 done criteria treats the User UI as a coherent product. Silent success
on a high-stakes action (save / hide a role) is the kind of friction that
undermines the matching workflow.

## V1 Scope

- The decision route appends `decision_status=<saved|hidden|cleared>` to
  the redirect URL.
- A small flash banner is rendered in `base.html` when the page's query
  string contains `decision_status` with one of the three accepted values.
  Unknown values are ignored (no banner).
- The banner uses `role="status"` and `aria-live="polite"` so screen
  readers announce it.

## Out Of Scope

- No session middleware / persistent flash store.
- No timeout / auto-dismiss JS — banner appears once and disappears on the
  next navigation.
- No styling beyond a `flash` class.
- No changes to non-decision flows (resume rewrite, source review, etc.).

## Data And Safety

`decision_status` is a server-controlled enum. The base template only
renders the banner when the value is one of the three known strings, so a
crafted query like `?decision_status=<script>` cannot cause anything other
than no banner — and the value never reaches the DOM since the rendered
text is a fixed lookup, not the raw query value.

## TDD And Review Gates

- Add a route test that POSTs `/jobs/{id}/decision` with `decision=saved`
  and `return_to=/dashboard?target_profile_id={id}`, asserts the redirect
  Location ends with `&decision_status=saved`, then GETs that location and
  asserts the rendered HTML contains the saved banner.
- Same test for `decision=hidden` → `decision_status=hidden`.
- Same test for `decision=clear` → `decision_status=cleared`.
- Add a test that GETs the dashboard with an unknown
  `?decision_status=garbage` and asserts NO `class="flash"` is rendered.
- Confirm tests fail before implementation.
- Implement the route change and template addition.
- Run focused tests, then full suite.
