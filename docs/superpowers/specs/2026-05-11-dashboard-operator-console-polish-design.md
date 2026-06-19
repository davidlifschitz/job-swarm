# Dashboard Operator Console Polish Design

Branch: `codex/ui-polish-operator-console`

## Goal

Make the local-first web dashboard feel more like an operator console for job
matching work while preserving existing source-policy, consent, decision, and
manual-submit behavior.

## Current Context

The app already has a left navigation shell, sticky runtime chips, a dashboard
primary/sidebar layout, saved-job search and sort, job detail pages, and admin
source surfaces. The weakest visual areas are the dashboard action block, the
company/job match table, the saved jobs page, and the job detail page. They
render the right information, but the hierarchy still feels flat and table-first.

## V1 Scope

- Add a dashboard command center above the primary work area with:
  - visible company count
  - visible match count
  - jobs waiting for fit review
  - fit-review availability state
- Convert dashboard action forms into visually distinct command cards while
  preserving form actions, consent text, disabled states, and button labels.
- Polish company groups and job rows with better density, row hover states,
  score/status treatments, note styling, and action layout.
- Upgrade saved jobs into a product surface with a page header, toolbar, framed
  card/list panel, and empty-state panel.
- Upgrade job detail into a two-column operator layout with distinct role, fit,
  decision, application, description, requirements, and referral panels.
- Keep all implementation in Jinja templates and `app.css`; avoid new client
  JavaScript or backend state unless a route contract needs it.

## Out Of Scope

- No new scraping sources.
- No LinkedIn or Indeed automation.
- No autonomous application submission.
- No auth, cookies, CAPTCHA, browser-profile, or live outreach changes.
- No frontend framework migration.

## Acceptance Criteria

- `/dashboard` renders a `dashboard-command-center` and command-card action
  forms while retaining `dashboard-actions`, `fit-review-action`,
  `decision-filters`, `company-group`, and existing form actions.
- `/dashboard/saved` renders a `saved-jobs-toolbar`, `saved-jobs-panel`, and
  styled empty state without changing CSV/filter behavior.
- `/jobs/{job_id}` renders `job-detail-shell`, `job-detail-grid`, and the
  existing application/referral/decision forms.
- `app.css` contains the new command center, command card, saved-job, and
  detail-page selectors with responsive behavior.
- Focused route tests pass.
- Browser smoke checks desktop and mobile dashboard views for rendering and
  overlap.

## Goal Review

Active goal: improve the `ml-job-swarm` UI and keep iterating with durable specs,
plans, implementation, verification, and publishing.

Verdict: aligned.

What works:
- The slice improves visible product quality without broadening source or apply
  behavior.
- It builds directly on the current Flask/Jinja architecture.
- It creates reusable route/CSS contracts for later UI polish.

Risks:
- Existing tests assert exact dashboard row markup in a few places, so the
  table structure must remain stable for this iteration.
- The dashboard has many forms; visual changes must not obscure LLM consent or
  manual-submit boundaries.

Decision: accept with the scoped table-preserving implementation above.
