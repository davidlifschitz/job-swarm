# Decision Flash Feedback Plan

**Goal:** Render a confirmation banner after save/hide/clear decisions.

**Architecture:** Append `decision_status=<saved|hidden|cleared>` to the
redirect Location in `set_job_decision`; render a `flash` block in
`base.html` driven by a fixed lookup of accepted values.

**Tech Stack:** FastAPI, Jinja, pytest.

---

## Files

- Modify: `ml_job_swarm/app.py` (`set_job_decision`)
- Modify: `ml_job_swarm/web/templates/base.html`
- Modify: `tests/test_routes_onboarding.py`

## Task 1: Tests First

- [x] **Step 1: Add failing tests**

In `tests/test_routes_onboarding.py`:

- `test_decision_redirect_appends_status_for_saved`: POST decision=saved,
  follow_redirects=False, assert Location contains
  `decision_status=saved`. Then GET that location and assert the response
  contains `class="flash"` and a string like `Job saved`.
- Same for `hidden` (banner: `Job hidden`).
- Same for `clear` (banner: `Decision cleared`).
- `test_dashboard_ignores_unknown_decision_status`: GET dashboard with
  `?decision_status=garbage` and assert `class="flash"` is NOT in the
  response.

- [x] **Step 2: Verify red**

```bash
uv run pytest tests/test_routes_onboarding.py -q
```

## Task 2: Implementation

- [x] **Step 1: Append decision_status on redirect**

In `set_job_decision`, after the try block, compute
`status_value = "cleared" if decision == "clear" else decision`. Get the
return path via `_safe_return_path`, then append `decision_status` using
`urllib.parse.urlencode` mindful of an existing `?`.

- [x] **Step 2: Render flash in base.html**

Add a `{% set _decision_status = ... %}` line that maps the request's
`decision_status` query param to a fixed message dict. Render
`<p class="flash" role="status" aria-live="polite">{{ message }}</p>`
above the page block when the param matches.

- [x] **Step 3: Verify focused and broad checks**

```bash
uv run pytest tests/test_routes_onboarding.py -q
uv run pytest -q
```

## Task 3: Publish

- [x] **Step 1: Commit, push, PR, merge**

```bash
git commit -m "Show decision confirmation flash after save/hide/clear"
```
