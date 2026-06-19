# Source Intake Preflight Plan

## Tests First

- Route test public ATS preview renders policy, inferred type, readiness, and
  queue action.
- Route test unknown public source renders manual-only/not-refreshable.
- Route test restricted source renders blocked guidance and no queue action.

## Implementation

- Add a `_source_intake_preview()` helper.
- Pass optional `company_name` and `source_url` query params into
  `/sources/new`.
- Update `source_new.html` with preview and hidden POST queue form.

## Verification

- Run focused admin source route tests.
- Run full `uv run pytest -q`.
- Browser-smoke `/sources/new` preview states.
