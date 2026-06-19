# CLI Friction Summary Plan

## Tests First

- Update success CLI tests to expect empty `friction_events` and
  `friction_status_codes`.
- Extend suspicious-empty coverage to expect an `empty_suspicious` event count.
- Add a public-registry failure test that raises a `RefreshError` with
  `status_code=403` and expects `blocked_response` and `403` counts.

## Implementation

- Capture `MAX(id)` from `ingestion_runs` before refresh.
- After refresh, query `source_friction_events` for rows with a later
  `ingestion_run_id`.
- Add event-type and status-code count maps to the CLI payload.

## Verification

- Run `uv run pytest tests/test_cli.py -q`.
- Run full `uv run pytest -q`.
- Run a live two-source public refresh smoke and inspect JSON output for
  `blocked_response` and `403` counts.
