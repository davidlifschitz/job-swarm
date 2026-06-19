# CLI Module Entrypoint Plan

## Tests First

- Add a subprocess test that runs `python -m ml_job_swarm.cli refresh` with
  fixture adapters.
- Assert the command returns `0`, emits parseable JSON, and refreshes one source.
- Confirm the test fails before implementation because stdout is empty.

## Implementation

- Add `if __name__ == "__main__": raise SystemExit(main())` at the bottom of
  `ml_job_swarm/cli.py`.
- Leave direct `main(...)` behavior and console-script metadata unchanged.

## Verification

- Run the focused CLI module test.
- Run all CLI tests.
- Run full `uv run pytest -q`.
- Manually run `uv run python -m ml_job_swarm.cli refresh` against a temporary
  fixture-backed database.
