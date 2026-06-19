# Local Referral Workspace Plan

Spec: `docs/superpowers/specs/2026-05-10-local-referral-workspace-design.md`

## Goal

Add local-only referral contacts tied to companies and visible from job detail.

## Ownership

- Controller-owned files:
  - `ml_job_swarm/store.py`
  - `ml_job_swarm/app.py`
  - `ml_job_swarm/web/templates/job_detail.html`
  - `tests/test_store_schema.py`
  - `tests/test_routes_onboarding.py`

## TDD Steps

1. Schema test: `contacts` and `referral_contacts` exist with safe fields.
2. Job detail test: renders add-contact form and no contacts empty state.
3. Add-contact route test:
   - posts contact name/title/email/note
   - redirects to job detail
   - stores one contact and link for the company
4. Job detail match test:
   - shows company contacts
   - hides contacts for other companies
   - does not render private resume text or prompt metadata
5. Implement schema, helper queries, route, and template.

## Verification

Focused:

```bash
uv run pytest tests/test_store_schema.py tests/test_routes_onboarding.py -q
```

Full:

```bash
uv run pytest
```

## Review Gates

- `goal-review`: confirm local referrals make the app more actionable without live discovery/outreach.
- `test-quality-review`: confirm tests prove local-only matching, company scoping, and privacy boundaries.
