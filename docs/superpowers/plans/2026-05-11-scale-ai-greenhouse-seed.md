# Scale AI Greenhouse Seed Source Plan

## Scope

Owner files:

- `data/seed_companies.json`
- `tests/test_catalog.py`

## TDD Steps

1. Add Scale AI to the verified extra public sources seed test.
2. Add `https://boards.greenhouse.io/scaleai` as a Greenhouse `extra_sources` entry.
3. Verify source policy and inferred provider type still match.
4. Live-smoke the Greenhouse adapter against the board and record the job count.

## Acceptance Checks

- Seed catalog includes Scale AI's direct Greenhouse extra source.
- `infer_source_type` returns `greenhouse` for the extra source.
- The public Greenhouse adapter can fetch at least one live job from the board.

## Integration Risks

The main risk is board slug drift. The seed test protects the intended URL, and the live adapter smoke proves it currently produces public jobs.

## Subagent Suitability

Single-controller slice. The change is small catalog data plus one existing catalog test.
