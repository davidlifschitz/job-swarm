# Application Prep Workspace Design

Branch: `codex/application-prep-workspace`

## Goal

Turn saved high-fit jobs into a local application prep workflow so the website helps the user get ready to apply while keeping final submission manual.

## Problem

Saved jobs and job detail pages expose external apply links, but the product does not create a local packet, checklist, or status trail. That leaves the user with a shortlist but no structured next action.

## V1 Scope

- Add an `application_packets` table keyed by job and target profile.
- Add a prep action from job detail and saved jobs.
- Build a deterministic packet from local data:
  - company and role
  - apply URL
  - source URL
  - fit score, label, recommendation
  - reasons and risks
  - notes
  - checklist items for review, manual submit, and status update
- Show packet status on job detail.
- Let the user mark a prepared packet as submitted after they manually submit externally.

## Safety Boundary

- V1 never clicks external apply buttons or submits applications.
- External apply links remain explicit user-click links.
- Packets must not include raw resume section text, private prompts, cookies, tokens, browser profiles, or LLM provider internals.
- Status changes are local audit/state only.

## Acceptance Criteria

- Job detail renders an application workspace with a prepare action.
- Saved jobs render a prepare action for each saved role.
- Preparing a packet creates or refreshes one packet and redirects back to job detail.
- Job detail shows checklist/status for a prepared packet.
- Marking submitted changes local status to `submitted`.
- Full tests pass.

## Later Scope

- Browser-assisted form prefill with user-visible manual submit.
- Company-specific application checklists.
- Cover letter generation with explicit LLM consent.
- Referral contact attachment to packets.
