---
name: design-spec-assets
description: Use when the user asks to save, organize, commit, publish, or keep generated design images, UI mockups, diagrams, or visual spec assets in this repository's design-specs folder.
---

# Design Spec Assets

## Overview

Use this skill to persist generated design visuals as durable repo artifacts instead of leaving them only under `$CODEX_HOME/generated_images`.

## Workflow

1. Identify the generated images or visual assets the user means.
2. Create `design-specs/` at the repository root if missing.
3. Copy selected assets into `design-specs/` with stable descriptive names:
   - `YYYY-MM-DD-<topic>-<kind>.png`
   - examples: `2026-05-08-v1-ui-mockup.png`, `2026-05-08-scoring-flow.png`
4. Keep originals in `$CODEX_HOME/generated_images`; do not delete them.
5. Add or update `design-specs/README.md` with a compact inventory:
   - filename
   - what it shows
   - source prompt or short generation note when useful
6. Do not commit local brainstorming server files such as `.superpowers/`.
7. Before staging, check for secrets and excluded local files:
   - `.env`
   - `.auth`
   - `.venv`
   - `jobs.db`
   - browser profiles, raw resumes, private identity data
8. If the user says “save in GitHub” or “publish”, use `github-push` after staging only the intended design assets and related skill/docs.

## Scope

Good assets:
- generated UI mockups
- architecture diagrams
- product concept maps
- design-spec screenshots
- approved visual variants

Avoid committing:
- discarded generations
- raw resume files
- prompt logs containing private data
- local server state such as `.superpowers/`
- hidden generated files outside the requested design artifact scope
