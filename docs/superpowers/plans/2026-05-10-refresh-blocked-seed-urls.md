# Refresh Blocked Seed URLs Plan

## Tests First

- Add a catalog regression for Adept and Citadel Securities current public
  careers URLs.
- Confirm the regression fails against the stale seed rows.

## Implementation

- Update `data/seed_companies.json`:
  - Adept: `https://www.adept.ai/about-careers/`
  - Citadel Securities: `https://www.citadelsecurities.com/careers/`
- Leave `ats_type` as `careers`.
- Allow hyphenated public careers slugs such as `about-careers`.
- Carry HTTP status codes from `HTTPError` through `RefreshError` into
  `source_friction_events.status_code`.

## Verification

- Run focused catalog tests.
- Run focused adapter and ingestion tests.
- Run full `uv run pytest -q`.
- Run a live public refresh smoke with only Adept and Citadel Securities and
  verify both blocked pages are logged with `status_code=403`.
