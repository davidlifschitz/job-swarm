# Real Public Refresh CLI Design

Branch: `codex/real-refresh-cli`

## Goal

Make the cron-friendly `ml-job-swarm refresh` command capable of refreshing
real reviewed public ATS sources instead of only fixture JSON.

## Why This Matters

The website can trigger real public ATS refreshes, but the CLI documented for
daily cron still requires `--fixture-dir`. That keeps the scheduled path as a
test harness rather than a real catalog refresh job.

## V1 Scope

- Add `--public-ats` to `ml-job-swarm refresh`.
- Keep `--fixture-dir` for deterministic local and CI fixture refreshes.
- Require either `--public-ats` or `--fixture-dir`.
- When `--public-ats` is used, build the registry with `public_ats_registry()`.
- Refresh only reviewed, enabled source types supported by the selected
  registry.
- Keep the existing JSON summary fields.
- Update README so daily refresh points at the public mode and fixture refresh
  is clearly marked as test/development mode.

## Safety Boundary

- No LinkedIn or Indeed scraping.
- No auth, cookies, CAPTCHA handling, hidden browser sessions, or profile state.
- No application submission or outreach.
- Public mode only uses existing source-policy checks and public ATS adapters.

## Acceptance Criteria

- `ml-job-swarm refresh --public-ats --db ... --seed ...` uses the public ATS
  registry.
- `ml-job-swarm refresh --fixture-dir ...` keeps current fixture behavior.
- Running refresh with neither adapter mode exits through argparse with a clear
  error.
- The command reports skipped reviewed sources when the registry does not
  support their source type.
- Tests avoid live network calls by monkeypatching the public registry.
- Full test suite passes.
