# Global Navigation Design

Branch: `claude/fix-website-e2e-Rj73P`

## Goal

Make the website fully usable end-to-end without the user having to type URLs.
Add a global navigation header rendered on every page so the user can move
between onboarding, dashboard, and admin source health from any view, and turn
the dashboard "Complete preferences before matching" empty state into a link
back to onboarding.

## Context

The V1 done criteria spec lists "first-run wizard" and a usable "User UI" with
company-grouped jobs and admin tooling. The routes and templates exist for the
full flow (`/onboarding`, `/dashboard`, `/jobs/{id}`, `/dashboard/saved`,
`/admin/sources`, `/admin/audit`, `/admin/runs`, `/admin/sources/friction`,
`/sources/new`), but `base.html` renders no navigation at all. The user can
walk forward through onboarding because each form posts to the next step, but
once they reach the dashboard there is no link back to onboarding to update
preferences or sideways to the admin pages. The empty dashboard
("Complete preferences before matching.") is a dead end: it tells the user
what to do but provides no link to do it.

## V1 Scope

- Add a `<nav>` block to `base.html` linking to `/onboarding`, `/dashboard`,
  and `/admin/sources` on every page.
- Mark the active link with `aria-current="page"` so it can be styled and is
  accessible.
- Preserve the existing dashboard query string (`target_profile_id` and
  `decision_filter`) when the dashboard link is rendered after the user
  completes onboarding, by allowing pages to pass a `dashboard_href` to
  `base.html`. When no profile is active, the link points to `/dashboard` with
  no query.
- In `dashboard.html`, when `onboarding_required` is truthy, render the
  empty-state message as an anchor pointing at `/onboarding`.

## Out Of Scope

- No styling changes beyond minimal nav markup; CSS in `app.css` may add a
  small `.global-nav` rule but no theme overhaul.
- No breadcrumb trail.
- No authentication or user identity in the nav.
- No mobile menu / hamburger interaction.

## Data And Safety

The nav is static HTML. It exposes only paths that are already public in this
local-first app. No new query parameters are introduced. The only dynamic
piece is the active-link detection, which compares `request.url.path` against
known route prefixes — no user data is read.

## TDD And Review Gates

- Add route tests asserting that `/onboarding`, `/dashboard`,
  `/admin/sources`, `/admin/audit`, `/admin/runs`,
  `/admin/sources/friction`, `/sources/new`, and `/jobs/{id}` all render the
  three nav links.
- Add a route test asserting that the active page is marked with
  `aria-current="page"`.
- Add a route test asserting that the dashboard empty state renders an anchor
  to `/onboarding` when `onboarding_required` is true.
- Confirm tests fail before implementation.
- Implement nav block in `base.html`, optional `dashboard_href` context, and
  the dashboard empty-state link.
- Run focused tests, then full suite.
