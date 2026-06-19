# Public Fetch Timeout Friction Plan

## Tests First

- Add public careers text fetch coverage for persistent timeout.
- Add public ATS JSON fetch coverage for persistent timeout.
- Keep existing retry-success and HTTP status-code tests green.

## Implementation

- In each default public fetch wrapper, check `_is_transient_timeout(exc)` after
  `_read_url_request` exhausts retries.
- Raise `RefreshError` with event type `timeout` for timeout-shaped failures.
- Leave HTTPError handling before the generic exception handler.

## Verification

- Run focused public adapter tests for timeout, retry, and HTTP status-code
  behavior.
- Run full `uv run pytest -q`.
