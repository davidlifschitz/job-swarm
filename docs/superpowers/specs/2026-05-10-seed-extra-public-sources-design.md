# Seed Extra Public Sources Design

## Goal

Let the default seed catalog use exact reviewed public ATS URLs while preserving
each company's normal careers page as its canonical display URL.

## Scope

The app already has real public ATS adapters, but the seed catalog can currently
import only one source per company. That forces generic company careers pages to
double as adapter sources, which weakens real-world refresh quality. This slice
adds optional `extra_sources` to seed companies so reviewed direct ATS board URLs
can be imported as additional `job_sources`.

This does not add authenticated scraping, cookies, CAPTCHA bypass, hidden
browser sessions, LinkedIn, Indeed, or final submit automation.

## Behavior

- Seed company rows keep `careers_url` and `ats_type` for the canonical careers
  page source.
- Optional `extra_sources` entries import additional reviewed `job_sources` for
  the same company.
- Every extra source is policy-gated exactly like the primary seed source.
- Import remains idempotent.
- The first verified seed subset uses direct public sources for OpenAI,
  Anthropic, Mistral AI, and CoreWeave.

## Tests

- Catalog parser accepts optional `extra_sources`.
- Importer creates primary and extra reviewed source rows for one company.
- Blocked extra sources are rejected.
- Default seed catalog contains the verified extra public source subset.

## Review Gates

Run goal-review and test-quality-review. Run focused catalog tests and the full
suite.
