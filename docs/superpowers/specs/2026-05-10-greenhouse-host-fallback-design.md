# Greenhouse Host Fallback Design

Branch: `codex/greenhouse-host-fallback`

## Goal

Let reviewed Greenhouse company career-page sources refresh through the public
Greenhouse board API when the board token can be safely inferred from the host.

## Why This Matters

The real public refresh CLI exposed a source-catalog drift pattern: many
seeded sources are marked `greenhouse`, but their URL is a company career page
instead of `boards.greenhouse.io/{board}`. The current adapter rejects those
before trying the public Greenhouse API, so daily refresh records manual-review
failures even for companies whose public board token is obvious.

## V1 Scope

- Keep native Greenhouse board URLs as the preferred exact path.
- For non-Greenhouse hosts, only infer a token when the path looks like a
  careers/jobs page.
- Strip common presentation subdomains such as `www`, `careers`, `jobs`, and
  `about`.
- Join short two-label hosts such as `x.ai` into `xai`.
- Return `None` for generic non-careers URLs so unsupported sources still fail
  before network calls.
- Do not add company-specific token maps in V1.

## Safety Boundary

- No LinkedIn or Indeed scraping.
- No browser sessions, cookies, auth, CAPTCHA handling, or hidden scraping.
- No application submission.
- Fallback uses the same public Greenhouse GET endpoint and fetcher as existing
  direct board URLs.
- Wrong inferred tokens fail through existing refresh friction.

## Acceptance Criteria

- `https://www.anthropic.com/careers` maps to the `anthropic` board token.
- `https://careers.airbnb.com/` maps to the `airbnb` board token.
- `https://about.gitlab.com/jobs/` maps to the `gitlab` board token.
- `https://x.ai/careers` maps to the `xai` board token.
- Non-careers pages such as `https://example.com/about` still raise
  `RefreshError` without calling the fetcher.
- Existing direct Greenhouse board behavior remains unchanged.
- Full test suite passes.
