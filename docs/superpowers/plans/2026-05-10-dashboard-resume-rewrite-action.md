# Dashboard Resume Rewrite Action Plan

Spec: `docs/superpowers/specs/2026-05-10-dashboard-resume-rewrite-action-design.md`

## Goal

Expose the existing section rewrite route from dashboard resume sections with explicit consent and redirect back to the active profile.

## Ownership

- Controller-owned files:
  - `ml_job_swarm/app.py`
  - `ml_job_swarm/web/templates/dashboard.html`
  - `tests/test_routes_resume_workspace.py`

## TDD Steps

1. Add a dashboard render test asserting each resume section includes a `/resume/rewrite` form, hidden `section_id`, hidden `target_profile_id`, and `llm_consent`.
2. Add a post test asserting rewrite with consent from dashboard redirects back to the active target profile and creates a draft suggestion.
3. Update `/resume/rewrite` to redirect when `target_profile_id` is present.
4. Add forms in `dashboard.html`.

## Verification

Focused:

```bash
uv run pytest tests/test_routes_resume_workspace.py -q
```

Full:

```bash
uv run pytest
```

## Acceptance Checks

- No raw `private_prompt` or LLM metadata appears in dashboard HTML.
- Missing consent still returns `400`.
- Missing client still returns `503`.
- Suggestion review remains local-only.

## Review Gates

- `goal-review`: confirm the website now exposes real resume editing without crossing the consent boundary.
- `test-quality-review`: confirm tests prove visible UI, route integration, and safety failure states.
