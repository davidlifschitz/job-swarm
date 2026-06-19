# Application Packet Summary

Date: 2026-05-10
Branch: `codex/application-packet-summary`

## Goal

Make a prepared application packet usable on the job detail page without
automating the final application submission.

## Scope

- Render packet summary fields from local `packet_json`.
- Show company, role, fit score, label, recommendation, reasons, risks, and
  manual submit URL.
- Keep the workflow manual-submit only.

## Out Of Scope

- Browser-based external application submission.
- Editing packet checklist state.
- Persisting or rendering raw private resume text.

## Acceptance

- After preparing a packet, job detail shows the packet summary and checklist.
- Manual submit URL opens as an external link.
- Private resume section text never appears in the page or packet output.
