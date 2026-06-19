# Product-grade first-run website design

## Goal

Make the existing local website feel like a working product for a new user without
claiming hosted production readiness that has not been verified.

## Observed gaps

- `/dashboard` with no target profile renders mostly blank space and one
  onboarding link.
- `/onboarding` has the required upload and preference forms, but it does not
  explain what the user should enter or what happens next.
- `/admin/sources` shows real seeded source data, but the coverage summary and
  wide table read like raw database output.
- No current deployed URL was found from the GitHub repo homepage, GitHub
  deployments API, or local deployment-related environment variables.

## V1 design

Add a deployment status object to the FastAPI app state and render it in the
global shell. It should default to local development with no public URL. If
`ML_JOB_SWARM_PUBLIC_URL`, `PUBLIC_URL`, `RENDER_EXTERNAL_URL`,
`RAILWAY_PUBLIC_DOMAIN`, `FLY_APP_NAME`, or `VERCEL_URL` is present, render the
configured public URL or provider-derived URL with an explicit hosted status.

Upgrade first-run dashboard content into a real empty state. When onboarding is
required, show a focused card with the next steps: upload a resume, set target
preferences, inspect public source health, and refresh once a profile exists.
Keep actions linked to `/onboarding` and `/admin/sources`.

Upgrade onboarding copy and controls in-place. Keep the same upload and
preference routes, but add product-context text, input placeholders, upload
support notes, and a next-step panel that sets expectations around local parsing,
consent-gated LLM use, and manual application submission.

Polish admin source health in the template and CSS only. The page should keep
the existing data and actions, but render source coverage as metric cards, make
status values badge-like, improve table readability, and keep long URLs readable.

## Acceptance

- First-run dashboard is useful with no target profile.
- Onboarding clearly guides resume upload and preference entry.
- Admin source health remains data-backed and reads cleanly at desktop width.
- Deployment status is visible and honest; no fake production claim is made.
- Existing source data is real seed/runtime data, not unlabeled fake product data.
- Focused route tests cover deployment status and first-run content.
- Browser screenshots verify `/onboarding`, `/dashboard`, and `/admin/sources`.
