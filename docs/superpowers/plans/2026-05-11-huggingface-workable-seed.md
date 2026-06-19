# Hugging Face Workable Seed Source Plan

## Scope

Owner files:

- `data/seed_companies.json`
- `tests/test_catalog.py`

## TDD Steps

1. Add Hugging Face to the verified extra public sources seed test.
2. Add `https://apply.workable.com/huggingface/` as a Workable extra source.
3. Verify source policy and inferred provider type.
4. Live-smoke the Workable adapter against the board and record the job count.

## Acceptance Checks

- Seed catalog includes Hugging Face's direct Workable extra source.
- `infer_source_type` returns `workable`.
- The public Workable adapter fetches current jobs from the board.

## Integration Risks

The main risk is Workable account slug drift. The seed test locks the intended source and live smoke verifies current behavior at implementation time.

## Subagent Suitability

Single-controller slice. This is a narrow seed-data update using existing adapter behavior.
