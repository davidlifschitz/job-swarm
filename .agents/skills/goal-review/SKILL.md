---
name: goal-review
description: Use when reviewing any proposed spec, plan, architecture note, data model, UI flow, implementation slice, or decision against the active thread goal before accepting or moving forward.
---

# Goal Review

## Purpose

Review proposed work against the current thread goal, not against a fixed product, MVP, or repository assumption.

The reviewer should first restate the active goal in one sentence from the current conversation, then judge whether the proposed output advances that goal cleanly.

## Goal Extraction

Before reviewing, identify:

- the user's latest stated goal
- explicit constraints and exclusions
- decisions already locked in during the thread
- what is V1/current scope versus later scope, if the thread defines phases
- any safety, privacy, compliance, or live-action boundaries

If the goal is ambiguous, say so and ask for one clarification instead of pretending the review can be precise.

## Review Method

For any proposed section or output, produce:

1. **Active Goal:** one sentence.
2. **Verdict:** `aligned`, `mostly aligned`, or `needs revision`.
3. **What Works:** bullets tied directly to the active goal.
4. **Gaps/Risks:** missing requirements, overreach, ambiguity, contradictions, stale assumptions, or scope creep.
5. **Recommended Changes:** concrete edits before accepting the output.
6. **Decision:** accept as-is, accept with edits, or revise before moving on.

## Standards

- Be strict about scope creep.
- Separate current-scope requirements from later-phase ideas.
- Prefer concrete edits over general criticism.
- Flag hidden assumptions and missing acceptance criteria.
- Flag any mismatch with locked user decisions.
- Flag safety or privacy violations immediately.
- Do not broaden the goal just because an idea is useful.

## Output Style

Keep review concise and actionable. Lead with the verdict. Do not rewrite the entire proposed section unless the user asks for a rewrite.
