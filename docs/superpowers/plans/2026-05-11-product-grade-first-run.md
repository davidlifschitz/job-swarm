# Product-grade first-run website implementation plan

## Scope

Improve the existing FastAPI/Jinja website surfaces without changing source
refresh, matching, scraping, or application-submission behavior.

## Files

- `ml_job_swarm/app.py`
- `ml_job_swarm/web/templates/base.html`
- `ml_job_swarm/web/templates/onboarding.html`
- `ml_job_swarm/web/templates/dashboard.html`
- `ml_job_swarm/web/templates/admin_sources.html`
- `ml_job_swarm/web/static/app.css`
- `tests/test_routes_app_shell.py`
- `README.md`

## Steps

1. Add failing route tests for default local deployment status, configured public
   URL rendering, first-run dashboard guidance, and admin metric cards.
2. Add deployment status detection in `app.py` and pass it through `_render`.
3. Update shell, onboarding, dashboard, and admin templates with the smallest
   markup needed for product-grade first-run guidance.
4. Add CSS for empty states, metric cards, deployment chips, badges, and readable
   source tables.
5. Document current deployment truth in the README.
6. Run focused tests, then Browser-smoke `/onboarding`, `/dashboard`, and
   `/admin/sources`.
