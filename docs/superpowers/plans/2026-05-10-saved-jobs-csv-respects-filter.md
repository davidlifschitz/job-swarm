# Saved Jobs CSV Respects Filter Plan

**Goal:** CSV export honours the page's `q` and `sort` params; export
link carries them.

**Architecture:** Extend `export_saved_jobs` to mirror `saved_jobs` query
parsing; reuse `_filter_saved_jobs` and `_sort_saved_jobs`. Update the
template link.

**Tech Stack:** FastAPI, Jinja, pytest.

---

## Files

- Modify: `ml_job_swarm/app.py` (`export_saved_jobs`)
- Modify: `ml_job_swarm/web/templates/saved_jobs.html`
- Modify: `tests/test_routes_onboarding.py`

## Task 1: Tests First

- [x] **Step 1: Add failing tests**

In `tests/test_routes_onboarding.py`:

- `test_saved_jobs_csv_respects_query_and_sort`: Seed three saved jobs
  (companies: OpenAI/Anthropic/Example), GET
  `/dashboard/saved.csv?target_profile_id=...&q=openai&sort=score`,
  parse CSV, assert only OpenAI rows present and ordered by descending
  fit_score.
- `test_saved_jobs_export_link_includes_filter_and_sort`: Seed at least
  one saved job, GET `/dashboard/saved?...&q=foo&sort=score`, assert
  `href="/dashboard/saved.csv?...&q=foo&sort=score"` (or equivalent
  query) appears in the rendered HTML.
- `test_saved_jobs_csv_unknown_sort_falls_back_to_recent`: Seed two
  saved jobs with different `decided_at`, GET CSV with
  `?sort=garbage`, assert rows in recent order.

- [x] **Step 2: Verify red**

```bash
uv run pytest tests/test_routes_onboarding.py -q
```

## Task 2: Implementation

- [x] **Step 1: Filter + sort the export**

In `export_saved_jobs`, accept `q: str = ""` and `sort: str = "recent"`.
Validate `sort` against the same set as `saved_jobs`. After fetching
`rows`, apply `_filter_saved_jobs` and `_sort_saved_jobs` before
iterating into the CSV writer.

- [x] **Step 2: Update the template link**

In `saved_jobs.html`, build the export href as
`/dashboard/saved.csv?target_profile_id={{ target_profile_id }}{% if query %}&q={{ query|urlencode }}{% endif %}{% if sort and sort != 'recent' %}&sort={{ sort }}{% endif %}`.

- [x] **Step 3: Verify focused and broad checks**

```bash
uv run pytest tests/test_routes_onboarding.py -q
uv run pytest -q
```

## Task 3: Publish

- [x] **Step 1: Commit, push, PR, merge**

```bash
git commit -m "Saved jobs CSV respects search and sort"
```
