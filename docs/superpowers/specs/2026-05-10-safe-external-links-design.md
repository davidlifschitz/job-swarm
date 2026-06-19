# Safe External Links Design

Branch: `claude/fix-website-e2e-Rj73P`

## Goal

Render every user-facing external link (job apply URLs, job source URLs)
with `rel="noopener noreferrer"` and `target="_blank"` so that:
1. The destination cannot read or manipulate `window.opener` (noopener).
2. The destination does not receive a Referer header that could leak the
   local job-board path or query (noreferrer).
3. Clicking out to apply does not destroy the user's place in the matching
   workflow (`target="_blank"`).

## Context

The V1 done criteria spec lists "Safety + Tests" as a column with explicit
items like "no LinkedIn/Indeed scraping", "no resume key logs", etc. Outbound
link safety is in the same family but currently unverified. Four external
links across two templates render with no safety attributes:

- `ml_job_swarm/web/templates/job_detail.html:20` — `apply_url`
- `ml_job_swarm/web/templates/job_detail.html:21` — `source_url`
- `ml_job_swarm/web/templates/saved_jobs.html:50` — `apply_url`
- `ml_job_swarm/web/templates/saved_jobs.html:51` — `source_url`

The admin pages render source URLs as text only (or in forms), so they are
not in scope. Internal site links (nav, dashboard, decision filters) stay
in-tab and need no `rel` attrs.

## V1 Scope

- Add `rel="noopener noreferrer" target="_blank"` to all four call sites
  above.
- Add tests asserting both attributes are present on the rendered apply and
  source links on the job detail page and the saved jobs page.

## Out Of Scope

- No URL allow-listing or scheme validation here (the canonical_url already
  flows through ingestion validation).
- No styling change to indicate "opens in new tab" — keep markup minimal.
- No changes to admin templates (no external link rendering).
- No CSV export field changes (the export already includes raw URLs).

## Data And Safety

The change is purely presentational and adds defence-in-depth on outbound
clicks. No new data is read, written, or logged. URLs are still
Jinja-escaped.

## TDD And Review Gates

- Add a route test asserting the rendered job detail page contains
  `rel="noopener noreferrer"` and `target="_blank"` for both the apply and
  source links.
- Add a route test asserting the rendered saved jobs page contains the same
  attributes for both links.
- Confirm tests fail before implementation.
- Implement the template additions.
- Run focused tests, then the full suite.
