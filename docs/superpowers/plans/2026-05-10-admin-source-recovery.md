# Admin Source Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a local admin recovery path that re-enables disabled job sources and audits the action.

**Architecture:** Reuse the existing source-admin route patterns in `ml_job_swarm/app.py`. Keep state in `job_sources.disabled_at`; write one `admin_audit_events` row per enable action; render the correct action button in `admin_sources.html`.

**Tech Stack:** FastAPI, Jinja, SQLite, pytest, Browser smoke verification.

---

## Files

- Modify: `tests/test_routes_admin_sources.py`
- Modify: `ml_job_swarm/app.py`
- Modify: `ml_job_swarm/web/templates/admin_sources.html`

## Task 1: Tests First

- [x] **Step 1: Add failing route tests**

Add tests to `tests/test_routes_admin_sources.py`:

```python
def test_enable_source_records_admin_audit_event():
    app = create_app()
    source_id = _seed_source(app.state.conn, disabled=True)
    client = TestClient(app)

    response = client.post(f"/admin/sources/{source_id}/enable", follow_redirects=False)

    source = app.state.conn.execute(
        "SELECT disabled_at FROM job_sources WHERE id = ?",
        (source_id,),
    ).fetchone()
    audit = app.state.conn.execute(
        "SELECT action, target_type, target_id FROM admin_audit_events"
    ).fetchone()
    assert response.status_code == 303
    assert source["disabled_at"] is None
    assert dict(audit) == {
        "action": "enable",
        "target_type": "job_source",
        "target_id": str(source_id),
    }
```

Also update `_seed_source(conn, disabled=False)` to optionally seed `disabled_at`.

- [x] **Step 2: Add route and template expectations**

Add assertions that disabled rows render an `Enable` button and no `Disable` button, while enabled rows still render `Disable`.

- [x] **Step 3: Verify red**

Run:

```bash
uv run pytest tests/test_routes_admin_sources.py -q
```

Expected: fail on missing `/admin/sources/{source_id}/enable` behavior and missing template button logic.

## Task 2: Implementation

- [x] **Step 1: Add enable route**

In `ml_job_swarm/app.py`, mirror the existing disable route:

```python
@app.post("/admin/sources/{source_id}/enable")
def enable_source(source_id: int):
    before = conn.execute(
        "SELECT disabled_at FROM job_sources WHERE id = ?",
        (source_id,),
    ).fetchone()
    if before is None:
        return HTMLResponse("Source not found", status_code=404)

    conn.execute(
        "UPDATE job_sources SET disabled_at = NULL WHERE id = ?",
        (source_id,),
    )
    after = conn.execute(
        "SELECT disabled_at FROM job_sources WHERE id = ?",
        (source_id,),
    ).fetchone()
    conn.execute(
        """
        INSERT INTO admin_audit_events (
          action,
          target_type,
          target_id,
          before_json,
          after_json
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            "enable",
            "job_source",
            str(source_id),
            json.dumps({"disabled_at": before["disabled_at"]}, sort_keys=True),
            json.dumps({"disabled_at": after["disabled_at"]}, sort_keys=True),
        ),
    )
    conn.commit()
    return RedirectResponse("/admin/sources", status_code=303)
```

- [x] **Step 2: Toggle admin action button**

In `ml_job_swarm/web/templates/admin_sources.html`, render `Enable` for disabled rows and `Disable` for enabled rows.

- [x] **Step 3: Verify focused and broad checks**

Run:

```bash
uv run pytest tests/test_routes_admin_sources.py -q
uv run pytest -q
```

Expected: all tests pass.

## Task 3: Browser And Publish

- [x] **Step 1: Browser smoke**

Start a local app with a temporary database that contains one disabled source. Open `/admin/sources` and verify `Enable` appears for that row.

- [x] **Step 2: Review gates**

Run goal-review against the change. Confirm it remains local-only, audited, and within V1 source-admin scope.

- [ ] **Step 3: Commit, push, PR, merge**

Commit message:

```bash
git commit -m "Add admin source recovery"
```

Push, open a PR, merge after local verification, then sync `main`.
