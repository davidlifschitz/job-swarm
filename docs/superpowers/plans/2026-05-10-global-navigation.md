# Global Navigation Implementation Plan

**Goal:** Make the website usable end-to-end by adding a global nav and a
clickable empty-state CTA.

**Architecture:** Add a `<nav class="global-nav">` block to `base.html` that
renders three links (Onboarding, Dashboard, Admin) with `aria-current="page"`
on the active route. Pass `request` to every template via the existing render
helper so the nav can compute the active link. Replace the dashboard
`onboarding_required` `<p>` with an `<a>` to `/onboarding`.

**Tech Stack:** FastAPI, Jinja, pytest.

---

## Files

- Modify: `ml_job_swarm/web/templates/base.html`
- Modify: `ml_job_swarm/web/templates/dashboard.html`
- Modify: `ml_job_swarm/app.py` (only if `request` is not already available
  in every template render)
- Modify: `tests/test_routes_onboarding.py`
- Modify: `tests/test_routes_admin_sources.py`

## Task 1: Tests First

- [x] **Step 1: Add failing tests**

In `tests/test_routes_onboarding.py` add a parametrized test that walks
`/onboarding`, `/dashboard`, `/jobs/{id}` (after a profile + job exist) and
asserts each response contains `href="/onboarding"`, `href="/dashboard"`, and
`href="/admin/sources"`. Assert that the link matching the requested page
carries `aria-current="page"`.

In `tests/test_routes_admin_sources.py` add the same nav assertion against
`/admin/sources`, `/admin/audit`, `/admin/runs`,
`/admin/sources/friction`, and `/sources/new`.

In `tests/test_routes_onboarding.py` add a test that hitting `/dashboard`
with no profile renders an anchor to `/onboarding` (not just plain text).

- [x] **Step 2: Verify red**

```bash
uv run pytest tests/test_routes_onboarding.py tests/test_routes_admin_sources.py -q
```

Expected: failures on missing nav links and missing anchor.

## Task 2: Implementation

- [x] **Step 1: Render nav in `base.html`**

Add a `<nav class="global-nav" aria-label="Primary">` containing three
anchors. Compute the active path from `request.url.path` and add
`aria-current="page"` when the path matches the link's prefix.

- [x] **Step 2: Ensure every render passes `request`**

Audit `app.py` to confirm every `render(...)` call includes `request`. The
existing `_render` helper already does. If any do not, add it.

- [x] **Step 3: Update dashboard empty state**

In `dashboard.html`, change:

```jinja
{% if onboarding_required %}
<p class="empty">Complete preferences before matching.</p>
{% elif not companies %}
```

to render `<a href="/onboarding">` inside the empty state when
`onboarding_required` is true.

- [x] **Step 4: Verify focused and broad checks**

```bash
uv run pytest tests/test_routes_onboarding.py tests/test_routes_admin_sources.py -q
uv run pytest -q
```

Expected: all green.

## Task 3: Publish

- [x] **Step 1: Commit, push, PR**

Commit message:

```bash
git commit -m "Add global navigation and onboarding empty-state link"
```

Push to `claude/fix-website-e2e-Rj73P`, open PR.
