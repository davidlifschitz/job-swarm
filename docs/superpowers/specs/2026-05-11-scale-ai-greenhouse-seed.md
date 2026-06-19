# Scale AI Greenhouse Seed Source

## Goal

Improve real public job coverage for Scale AI by adding a verified direct Greenhouse board as a reviewed extra source.

## Problem

The seed catalog had Scale AI only as a generic careers page. Live probing showed the public Greenhouse board at `https://boards.greenhouse.io/scaleai` returns current jobs through the existing Greenhouse adapter, while the generic careers page can be weaker for ingestion.

## V1 Behavior

- Preserve the canonical Scale AI careers URL.
- Add the verified Greenhouse board as an extra reviewed public source.
- Keep source policy unchanged and avoid LinkedIn, Indeed, auth-gated pages, CAPTCHA handling, or browser scraping.

## Review Gates

- `goal-review`: passes if the change improves real-world public catalog coverage without expanding scraping scope.
- `test-quality-review`: passes if seed tests prove the extra source is present and policy/provider inference still match.
