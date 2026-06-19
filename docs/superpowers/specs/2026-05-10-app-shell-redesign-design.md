# App Shell Redesign Design

Branch: `codex/app-shell-redesign`

## Goal

Make the website feel like a real local-first job operations product while
preserving the current public-ATS, resume, fit-review, application-packet, and
admin workflows.

## Inputs

- Browser reference scan: Linear for dense product-system polish, Vercel for
  crisp controls, Raycast for strong action affordances, and Notion for clean
  workspace hierarchy.
- Generated visual direction:
  `design-specs/2026-05-10-app-shell-redesign-mockup.png`.

## V1 Scope

- Replace the 90s-style page skin with a restrained app shell:
  - left navigation rail
  - compact top status strip
  - full-width page headers
  - dense panels and tables
  - status chips, badges, and action bars
- Preserve existing route behavior, form actions, decision links, consent
  boundaries, and test-dependent class names.
- Improve dashboard layout so job matches, resume workspace, application prep,
  and source friction feel like parts of one operating surface.
- Improve admin/source and onboarding styling with the same system.

## Safety Boundary

- No new scraping sources.
- No LinkedIn or Indeed scraping.
- No auth, CAPTCHA, cookies, hidden browser sessions, or autonomous submission.
- No private resume/contact data leaves the local app.
- Styling must not hide consent text or manual-submit boundaries.

## Acceptance Criteria

- `base.html` renders an app shell while preserving `global-nav`, active links,
  flash behavior, and `main.page`.
- Dashboard renders a page header, action bar, primary match column, and
  supporting sidebar wrappers.
- Admin sources renders as an operational source-health surface with a page
  header, action bar, refresh action, and framed source tables.
- Existing onboarding, dashboard, admin, resume, and saved-job route tests pass.
- Browser smoke verifies dashboard and admin screens render without obvious
  overlap at desktop and mobile widths.
- Full test suite passes.
