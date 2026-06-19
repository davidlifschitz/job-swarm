# Lever Host Fallback Design

Branch: `codex/lever-host-fallback`

## Goal

Let reviewed Lever company career-page sources refresh through the public Lever
postings API when the site slug can be safely inferred from the host.

## Why This Matters

After public ATS and Greenhouse fallback work, the full seed refresh still has
one Lever source failure: Mistral AI is marked `lever` but uses
`https://mistral.ai/careers` instead of `https://jobs.lever.co/mistral`.
The public Lever API supports `mistral`, so this is the same source-catalog drift
shape as Greenhouse.

## V1 Scope

- Keep native `jobs.lever.co/{site}` and `jobs.eu.lever.co/{site}` behavior.
- For non-Lever hosts, infer a site slug only when the path or host looks like a
  careers/jobs page.
- Strip common presentation prefixes and return the company host label.
- Join short two-label hosts such as `x.ai` if encountered later.
- Do not add company-specific maps in V1.

## Safety Boundary

- No LinkedIn or Indeed scraping.
- No browser sessions, cookies, auth, CAPTCHA handling, or hidden scraping.
- No application submission.
- Fallback uses the same public Lever GET endpoint and fetcher as existing
  direct Lever URLs.
- Wrong inferred slugs fail through existing refresh friction.

## Acceptance Criteria

- `https://mistral.ai/careers` maps to the `mistral` Lever site slug.
- `https://careers.example.com/` maps to `example` when the source is reviewed
  as Lever.
- Non-careers pages such as `https://example.com/about` still raise
  `RefreshError` without calling the fetcher.
- Existing direct Lever behavior remains unchanged.
- Full test suite passes.
