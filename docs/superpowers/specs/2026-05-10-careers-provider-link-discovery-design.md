# Careers Provider Link Discovery Design

## Goal

Turn static public company careers pages into useful ingestion sources when they link to supported public ATS providers.

## Why This Matters

Many seed companies expose a clean `/careers` page that contains little or no JobPosting JSON-LD, but links directly to Greenhouse, Lever, Ashby, Workday, SmartRecruiters, or Workable. Before this, those sources could refresh to suspicious empty results even though the real public job board was one click away. Discovering explicit provider links makes the website do real provider-backed work without relying on authenticated scraping.

## V1 Scope

- Fetch one already-reviewed public careers page.
- Extract static HTML anchor links.
- Normalize relative links against the source URL.
- Classify every discovered link with the existing source policy before using it.
- Delegate explicit public provider links to the matching supported adapter.
- Canonicalize provider board URLs so filtered links do not trigger duplicate board refreshes.
- Combine JSON-LD jobs and delegated provider jobs in one refresh.
- Ignore restricted, search-proxy, auth, CAPTCHA, mailto, and unsupported links.

## Safety Boundaries

- Static one-page HTML only.
- No browser crawling, hidden sessions, cookies, auth, CAPTCHA handling, search-result scraping, LinkedIn, Indeed, or final submit automation.
- No guessing provider slugs from arbitrary text.
- No private resume/profile data is involved.

## Acceptance Criteria

- A careers page linking to a public supported provider returns provider jobs.
- Multiple filter links to the same provider board produce one delegated provider refresh.
- Restricted/search/auth/CAPTCHA links are ignored before any adapter runs.
- Delegated jobs insert through the normal refresh path.
- Empty public careers pages still use existing suspicious-empty diagnostics.

## Review Gates

- `goal-review`: confirm this advances real public job ingestion without crossing the compliance boundary.
- `test-quality-review`: confirm unit and integration tests prove provider delegation and safety filtering.
