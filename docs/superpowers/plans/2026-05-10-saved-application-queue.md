# Saved Application Queue Status Plan

## Tests First

- Add saved page coverage for prepared and submitted packet statuses.
- Add CSV coverage for packet status/manual-submit URL.

## Implementation

- Extend `saved_job_export_rows()` with a left join to `application_packets`.
- Add CSV fields for `packet_status` and `manual_submit_url`.
- Add an Application column to `saved_jobs.html`.

## Verification

- Run focused saved-job route tests.
- Run full `uv run pytest -q`.
- Browser-smoke saved jobs with prepared and submitted rows.
