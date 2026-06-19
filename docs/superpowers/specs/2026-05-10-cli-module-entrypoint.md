# CLI Module Entrypoint

Date: 2026-05-10
Branch: `codex/cli-module-entrypoint`

## Goal

Make the cron-friendly refresh command work when invoked through Python module
execution.

## Problem

`python -m ml_job_swarm.cli ...` exited successfully without running the CLI
because the module did not call `main()` when executed as `__main__`. That made
one common cron invocation path a silent no-op.

## Scope

- Add a module entrypoint guard that raises `SystemExit(main())`.
- Add a fixture-backed subprocess regression for `python -m ml_job_swarm.cli
  refresh`.

## Out Of Scope

- Changing console-script packaging.
- Running live public ATS network refreshes in tests.
- Changing refresh behavior or source policy.

## Acceptance

- Module execution emits the same refresh JSON shape as the console command.
- The command writes jobs into the requested SQLite database.
- Full tests pass.
