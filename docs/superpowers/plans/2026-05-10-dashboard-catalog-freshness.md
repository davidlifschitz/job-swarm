# Dashboard Catalog Freshness Plan

**Goal:** Render "Catalog refreshed: <timestamp> UTC" on the dashboard.

**Architecture:** Add a `_latest_succeeded_run_finished_at(conn)` helper in
`app.py`; pass `catalog_refreshed_at` to all three `_render` calls in the
dashboard route; render a small `.catalog-freshness` line in
`dashboard.html`.

**Tech Stack:** FastAPI, Jinja, SQLite, pytest.

---

## Files

- Modify: `ml_job_swarm/app.py`
- Modify: `ml_job_swarm/web/templates/dashboard.html`
- Modify: `tests/test_routes_onboarding.py`

## Task 1: Tests First

- [x] **Step 1: Add failing tests**

In `tests/test_routes_onboarding.py`:

- `test_dashboard_renders_catalog_freshness_from_latest_succeeded_run`:
  Seed an older succeeded run, a newer succeeded run, and a running
  row; GET dashboard; assert `class="catalog-freshness"` and the newer
  finished_at appear in the response.
- `test_dashboard_freshness_message_when_no_runs`: Seed nothing; GET
  dashboard; assert "Catalog has not been refreshed yet." appears.
- `test_dashboard_onboarding_state_still_shows_freshness`: GET dashboard
  with no profile; assert the freshness line is present.

- [x] **Step 2: Verify red**

```bash
uv run pytest tests/test_routes_onboarding.py -q
```

## Task 2: Implementation

- [x] **Step 1: Add helper**

```python
def _latest_succeeded_run_finished_at(conn) -> str | None:
    row = conn.execute(
        "SELECT finished_at FROM ingestion_runs "
        "WHERE status = 'succeeded' AND finished_at IS NOT NULL "
        "ORDER BY id DESC LIMIT 1"
    ).fetchone()
    return row["finished_at"] if row else None
```

- [x] **Step 2: Pass it to the dashboard renders**

In every `_render(... "dashboard.html" ...)` call (three of them), add
`catalog_refreshed_at=_latest_succeeded_run_finished_at(conn)`.

- [x] **Step 3: Render in template**

In `dashboard.html` immediately after `<h1>Job matches</h1>`, add:

```jinja
{% if catalog_refreshed_at %}
<p class="catalog-freshness">Catalog refreshed: {{ catalog_refreshed_at }} UTC</p>
{% else %}
<p class="catalog-freshness">Catalog has not been refreshed yet.</p>
{% endif %}
```

- [x] **Step 4: Verify focused and broad checks**

```bash
uv run pytest tests/test_routes_onboarding.py -q
uv run pytest -q
```

## Task 3: Publish

- [x] **Step 1: Commit, push, PR, merge**

```bash
git commit -m "Show catalog last-refreshed timestamp on dashboard"
```
