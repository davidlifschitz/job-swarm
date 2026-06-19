# Application Packet Summary Plan

## Tests First

- Add job-detail route coverage for a prepared packet summary.
- Assert fit metadata, reasons, risks, and manual submit URL render.
- Assert private resume text remains absent.

## Implementation

- Extend `job_detail.html` application workspace to render
  `application_packet.packet`.
- Keep existing status update and prepare forms unchanged.

## Verification

- Run focused onboarding route tests.
- Run full `uv run pytest -q`.
- Browser-smoke prepared packet detail page.
