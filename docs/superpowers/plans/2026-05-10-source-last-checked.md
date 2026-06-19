# Source Last-Checked Visibility Plan

**Goal:** Show each source's `last_checked_at` on the admin source health page.

**Architecture:** Extend `_source_health_rows` to include the column; add a
`Last checked` column to `admin_sources.html`.

**Tech Stack:** FastAPI, Jinja, SQLite, pytest.

---

## Files

- Modify: `ml_job_swarm/app.py` (`_source_health_rows`)
- Modify: `ml_job_swarm/web/templates/admin_sources.html`
- Modify: `tests/test_routes_admin_sources.py`

## Task 1: Tests First

- [x] **Step 1: Add failing test**

In `tests/test_routes_admin_sources.py` add a test that seeds two sources
(one with `last_checked_at = '2026-05-09T12:00:00'`, one with NULL) and
asserts the rendered admin page contains the timestamp for the first source
and the string `Never` for the second, plus the column header
`Last checked`.

- [x] **Step 2: Verify red**

```bash
uv run pytest tests/test_routes_admin_sources.py -q
```

## Task 2: Implementation

- [x] **Step 1: SELECT `last_checked_at`**

Add `job_sources.last_checked_at` to the SELECT in `_source_health_rows`.

- [x] **Step 2: Render column**

In `admin_sources.html` add a `<th>Last checked</th>` and a `<td>` rendering
`{{ source.last_checked_at or "Never" }}`.

- [x] **Step 3: Verify focused and broad checks**

```bash
uv run pytest tests/test_routes_admin_sources.py -q
uv run pytest -q
```

## Task 3: Publish

- [x] **Step 1: Commit, push, PR**

```bash
git commit -m "Show source last-checked timestamps in admin health"
```
