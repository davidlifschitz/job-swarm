# Hugging Face Workable Seed Source

## Goal

Improve real public job coverage for Hugging Face by adding its verified direct Workable board as a reviewed extra source.

## Problem

The seed catalog had Hugging Face only as `https://huggingface.co/jobs`, which currently behaves like a generic careers page and does not reliably yield public job postings through the generic adapter. The public Workable board at `https://apply.workable.com/huggingface/` returns current jobs through the existing Workable adapter.

## V1 Behavior

- Preserve the canonical Hugging Face careers URL.
- Add the Workable board as a reviewed public extra source.
- Keep the source inside the existing public-source policy boundary with no auth, cookies, CAPTCHA handling, hidden browser sessions, LinkedIn, or Indeed scraping.

## Review Gates

- `goal-review`: passes if this increases real public job ingestion without broadening scraping scope.
- `test-quality-review`: passes if seed tests cover presence, policy allowance, provider inference, and a live adapter smoke confirms current jobs.
