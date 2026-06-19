# Onboarding Preferences Inline Validation Plan

**Goal:** Re-render the onboarding form with inline errors and preserved
values when `/preferences` validation fails.

**Architecture:** In `save_preferences`, build an `errors` dict keyed by
preference id (plus optional form-level error) and call `_render` on
`onboarding.html` with status 400. Update `onboarding.html` to render errors
and repopulate inputs. Update tests.

**Tech Stack:** FastAPI, Jinja, pytest.

---

## Files

- Modify: `ml_job_swarm/app.py` (`save_preferences`)
- Modify: `ml_job_swarm/web/templates/onboarding.html`
- Modify: `tests/test_routes_onboarding.py`

## Task 1: Tests First

- [x] **Step 1: Add failing test**

Add a new test that POSTs `/preferences` with `role` and `level` only, then
asserts:
- status 400
- `<form action="/preferences"` is present (form re-rendered, not bare error)
- `class="field-error"` appears for the missing fields
- `value="Machine Learning Engineer"` and `value="senior"` are present
  (submitted values preserved)
- error text mentions `location`, `work mode`, `company stage`

Update `test_preferences_missing_disables_matching` to assert the form is
present and a recognisable error message is shown, instead of just
"Missing preference".

- [x] **Step 2: Verify red**

```bash
uv run pytest tests/test_routes_onboarding.py -q
```

## Task 2: Implementation

- [x] **Step 1: Re-render onboarding on validation failure**

In `save_preferences` (`ml_job_swarm/app.py:235`), instead of
`HTMLResponse("Missing preference: ...", 400)`, build an `errors` dict
mapping each missing preference id to a human-readable message, capture
submitted values, and return `_render(request, "onboarding.html", ...,
status_code=400)`. Same pattern for the missing resume asset case (a
form-level error).

- [x] **Step 2: Render errors and preserved values in template**

In `onboarding.html`, when `errors` is provided, render the message above
each input and add `class="field-error"` / `aria-invalid="true"` to the
affected field. Set `value="{{ submitted.role|default('') }}"` etc.

- [x] **Step 3: Verify focused and broad checks**

```bash
uv run pytest tests/test_routes_onboarding.py -q
uv run pytest -q
```

## Task 3: Publish

- [x] **Step 1: Commit, push, PR, merge**

```bash
git commit -m "Re-render onboarding form with inline preference errors"
```
