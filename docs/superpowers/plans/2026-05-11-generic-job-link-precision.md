# Generic Job Link Precision Plan

## Scope

Owner files:

- `ml_job_swarm/adapters.py`
- `tests/test_adapters_public_ats.py`

## TDD Steps

1. Add a failing adapter test proving location, category, list-page, and unresolved template links are ignored.
2. Keep the existing same-domain job-detail extraction test green.
3. Add a small path-segment guard in `_looks_like_job_detail_path`.
4. Run focused adapter tests, then the full suite.

## Acceptance Checks

- Generic fallback does not emit fake jobs for `/jobs/locations/*`, `/jobs/categories/*`, `/careers/list`, or `/jobs/{{template}}`.
- Generic fallback still emits a real same-domain detail link such as `/careers/software-engineer-ai`.
- No live network behavior changes.

## Integration Risks

The main risk is over-filtering a legitimate job URL that contains a facet word. The guarded terms are reserved for common index dimensions, not role slugs, and the provider-specific adapters remain unaffected.

## Subagent Suitability

Single-controller slice. The implementation is small and touches one shared adapter heuristic, so parallel writes would create avoidable merge risk.
