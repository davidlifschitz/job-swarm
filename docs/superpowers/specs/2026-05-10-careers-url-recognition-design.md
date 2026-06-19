# Careers URL Recognition Design

Branch: `codex/careers-url-recognition`

## Goal

Reduce false skips for common public employer careers URLs before the JSON-LD
adapter has a chance to parse structured `JobPosting` data.

## V1 Scope

- Treat `.jobs` hosts as careers pages.
- Treat `/open-positions/` and `/career-opportunities/` paths as careers pages.
- Keep generic non-careers URLs rejected before fetch.

## Acceptance Criteria

- The JSON-LD adapter accepts common public careers shapes seen in the seed
  catalog probe.
- Existing unsupported URL tests continue passing.
- Full test suite passes.
