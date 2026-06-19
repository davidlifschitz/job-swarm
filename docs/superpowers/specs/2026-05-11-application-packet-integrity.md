# Application packet integrity

## Goal

Make the manual-submit packet preserve real workflow state and carry accepted
resume rewrite work into the prep artifact.

## Problem

The site can mark an application packet as submitted, but pressing Prepare
application again rewrites the row back to `prepared`. The packet also tells the
user to review resume suggestions without carrying accepted rewrite text into
the local packet.

## V1 Design

- Re-preparing a packet refreshes packet JSON and checklist data but preserves
  `submitted` status once the user has marked the manual submit complete.
- Application packet JSON includes accepted resume rewrite suggestions for the
  active target profile as sanitized section-level records.
- Job detail renders accepted resume rewrites from the packet.
- Submitted packets do not keep presenting a primary prepare action.

## Safety

- No external submission is automated.
- Raw parsed resume text stays out of packet JSON and rendered packet HTML.
- Only accepted suggestions are copied into the packet.

## Acceptance

- A submitted packet remains submitted after re-prepare.
- Accepted resume rewrite suggestions appear in packet JSON and job detail.
- Raw resume text does not appear in packet JSON or packet HTML.
