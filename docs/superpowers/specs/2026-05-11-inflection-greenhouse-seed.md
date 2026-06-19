# Inflection AI Greenhouse Seed Source

## Goal

Improve real public job coverage for Inflection AI by adding its verified direct Greenhouse board as a reviewed extra source.

## Problem

The seed catalog had Inflection AI only as a generic careers page. Current public Greenhouse job embeds resolve to the board `inflectionai`, and the existing Greenhouse adapter can fetch that board without auth, cookies, CAPTCHA handling, or browser automation.

## V1 Behavior

- Preserve `https://inflection.ai/careers` as the canonical careers URL.
- Add `https://boards.greenhouse.io/inflectionai` as a Greenhouse extra source.
- Keep the source inside the existing public-source policy boundary.

## Review Gates

- `goal-review`: passes if this increases real public job ingestion without broadening scraping scope.
- `test-quality-review`: passes if seed tests cover presence, policy allowance, and provider inference, with a live adapter smoke for current job count.
