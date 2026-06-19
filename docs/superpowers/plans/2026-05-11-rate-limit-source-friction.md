# Rate-Limit Source Friction Plan

## Scope

Owner files:

- `ml_job_swarm/adapters.py`
- `ml_job_swarm/ingest.py`
- `tests/test_adapters_public_ats.py`
- `tests/test_ingest.py`
- `tests/test_routes_admin_sources.py`

## TDD Steps

1. Add a failing adapter test for HTTP 429 classification across JSON, HTML, and POST fetchers.
2. Add a failing ingestion test that rate-limited failures store a retry/cadence recommendation.
3. Add an admin route test that the latest rate-limit recommendation is visible.
4. Implement the smallest shared HTTP-error classifier and friction-detail helper.
5. Run focused tests, full suite, and a live refresh smoke.

## Acceptance Checks

- HTTP 429 becomes `rate_limited`, not `blocked_response`.
- `status_code=429` is preserved.
- Admin source health shows a retry/cadence recommendation.
- HTTP 403 remains `blocked_response`.

## Integration Risks

The main risk is overgeneralizing all HTTP failures. The classifier only special-cases 429 and leaves other HTTP errors unchanged.

## Subagent Suitability

Single-controller slice. The change touches shared adapter and ingestion error contracts and is small enough to keep integrated locally.
