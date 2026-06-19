# Careers Provider Link Discovery Implementation Plan

Spec: `docs/superpowers/specs/2026-05-10-careers-provider-link-discovery-design.md`

## Goal

Delegate explicit public ATS links found on static company careers pages into the existing provider adapters.

## Ownership

- Controller-owned files:
  - `ml_job_swarm/adapters.py`
  - `tests/test_adapters_public_ats.py`
  - `tests/test_ingest.py`
  - this spec and plan pair

## TDD Steps

1. Add adapter tests for provider-link delegation and restricted/auth/search link rejection.
2. Add an ingestion test proving delegated provider jobs insert through `refresh_source`.
3. Add provider-adapter injection to `CareersJsonLdAdapter`.
4. Extract static HTML anchors and normalize relative URLs.
5. Classify discovered links through `classify_source_url`.
6. Canonicalize provider board URLs to avoid duplicate provider refreshes.
7. Delegate only supported public provider URLs.
8. Run focused adapter/ingest tests and the full suite.

## Verification

```bash
uv run pytest tests/test_adapters_public_ats.py tests/test_ingest.py -q
uv run pytest -q
```
