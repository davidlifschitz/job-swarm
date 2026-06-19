# Dashboard Rules Preview Plan

## Tests First

- Unit test `rules_preview_jobs` ranks an unreviewed matching job and does not
  persist review rows.
- Unit test obvious mismatch jobs are excluded.
- Route test dashboard renders the preview while `fit_gate_client` is `None`.

## Implementation

- Add a `RulesPreviewJob` dataclass and `rules_preview_jobs()`.
- Reuse existing `apply_rules()` and target-profile conversion helpers.
- Pass preview rows into `dashboard.html`.
- Render a compact preview table above the unreviewed fit-review queue.

## Verification

- Run focused filtering and dashboard tests.
- Run full `uv run pytest -q`.
- Browser-smoke dashboard with a temp local DB containing a reviewed public job.
