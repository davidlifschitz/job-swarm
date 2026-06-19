# Dashboard Public Refresh Implementation Plan

Spec: `docs/superpowers/specs/2026-05-10-dashboard-public-refresh-design.md`

## Goal

Add a refresh-only dashboard action so public source ingestion can run independently of LLM fit review.

## Ownership

- Controller-owned files:
  - `ml_job_swarm/app.py`
  - `ml_job_swarm/web/templates/dashboard.html`
  - `tests/test_routes_dashboard.py`
  - this spec and plan pair

## TDD Steps

1. Add route tests first.
   - Dashboard renders `Refresh public sources`.
   - Posting `/dashboard/refresh-sources` without `llm_consent` refreshes supported public sources.
   - Posting the refresh-only action works with `fit_gate_client = None`.
   - Existing `Find matches` consent/provider gates remain covered.
2. Implement the route.
   - Require `target_profile_id`.
   - Refresh only registry-supported reviewed sources.
   - Count unsupported reviewed sources as skipped.
   - Redirect with source/job summary fields and zero review counts.
3. Update the dashboard template.
   - Add a refresh-only form.
   - Keep separate LLM consent forms for fit review and find matches.
4. Run review gates and verification.

## Acceptance Checks

- Public refresh can populate jobs before LLM fit review.
- No private prompt or resume content is sent by refresh-only.
- Unsupported reviewed sources do not trigger fallback scraping.

## Verification

```bash
uv run pytest tests/test_routes_dashboard.py -q
uv run pytest -q
```
