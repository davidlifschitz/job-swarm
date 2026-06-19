# Source Intake Preflight

Date: 2026-05-10
Branch: `codex/source-intake-preflight`

## Goal

Make source intake explain whether a submitted company source can be refreshed
before it enters the admin review queue.

## Scope

- Add a preview state to `/sources/new`.
- Show policy mode/reason, normalized URL, inferred source type, and adapter
  support.
- Allow queueing only from a safe preview state.
- Keep restricted sources blocked by policy and visible as non-queueable.

## Out Of Scope

- Live scraping during intake.
- CAPTCHA/auth/cookie handling.
- Auto-approving user-submitted sources.

## Acceptance

- Public ATS URLs show refresh-ready preflight and a queue action.
- Unknown public company links show manual-only/not-refreshable preflight.
- LinkedIn/Indeed or restricted-proxy sources show blocked preflight and no
  queue action.
- Existing POST queue behavior remains safe and server-side enforced.
