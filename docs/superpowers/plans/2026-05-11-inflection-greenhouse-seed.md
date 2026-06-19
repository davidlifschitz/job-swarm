# Inflection AI Greenhouse Seed Source Plan

## Scope

Owner files:

- `data/seed_companies.json`
- `tests/test_catalog.py`

## TDD Steps

1. Add Inflection AI to the verified extra public sources seed test.
2. Add `https://boards.greenhouse.io/inflectionai` as a Greenhouse extra source.
3. Verify source policy and inferred provider type.
4. Live-smoke the Greenhouse adapter against the board and record the job count.

## Acceptance Checks

- Seed catalog includes Inflection AI's direct Greenhouse extra source.
- `infer_source_type` returns `greenhouse`.
- The public Greenhouse adapter fetches current jobs from the board.

## Integration Risks

The main risk is Greenhouse board slug drift. The seed test locks the intended source and live smoke verifies current behavior at implementation time.

## Subagent Suitability

Single-controller slice. This is a narrow seed-data update with existing adapter coverage.
