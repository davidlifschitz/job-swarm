# Resilient Fit Review Batch Design

## Goal

Let first-run matching continue reviewing jobs when one fit-review call fails.

## Scope

The first-run match action may process hundreds of real jobs. A single provider
timeout, malformed response, or job-specific fit-review failure should not stop
the entire batch. This slice adds a resilient batch review path for the
first-run match action while preserving the existing strict `/dashboard/review-jobs`
behavior.

This does not add new LLM providers, send data without consent, retry private
LLM calls indefinitely, authenticated scraping, cookies, CAPTCHA bypass,
LinkedIn, Indeed, or final submit automation.

## Behavior

- Strict `review_jobs_for_profile()` keeps raising on provider/runtime failures.
- A new resilient profile-review path catches per-job failures, continues with
  remaining jobs, and returns counts.
- Failed per-job LLM metadata remains recorded by the existing fit-review code.
- `/dashboard/find-matches` uses the resilient path and includes review failure
  counts in the dashboard redirect and summary panel.

## Tests

- Filtering test proves one failed fit review does not stop a later successful
  job review.
- Dashboard route test proves first-run matching redirects with both successful
  review count and review failure count.

## Review Gates

Run goal-review and test-quality-review. Run focused fit/dashboard tests and the
full suite.
