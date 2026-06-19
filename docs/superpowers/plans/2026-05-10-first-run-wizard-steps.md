# First-Run Wizard Step Indicator Plan

**Goal:** Add a 3-step progress indicator to the onboarding page so users
see they are in a wizard and which step is active.

**Architecture:** Render an `<ol class="wizard-steps">` at the top of
`onboarding.html` with three `<li>`s (`upload`, `preferences`, `matches`).
The active step is computed in the template from `resume_asset_id`.

**Tech Stack:** Jinja, pytest.

---

## Files

- Modify: `ml_job_swarm/web/templates/onboarding.html`
- Modify: `tests/test_routes_onboarding.py`

## Task 1: Tests First

- [x] **Step 1: Add failing tests**

Add a test that GET `/onboarding` (no resume yet) renders the three step
labels and marks the upload step `aria-current="step"`. Add a test that GET
`/onboarding?resume_asset_id=42` marks the preferences step
`aria-current="step"` and the upload step is NOT current. Both tests should
also assert all three `data-step-id` values are present.

- [x] **Step 2: Verify red**

```bash
uv run pytest tests/test_routes_onboarding.py -q
```

## Task 2: Implementation

- [x] **Step 1: Render wizard list**

In `onboarding.html` add an `<ol class="wizard-steps">` block immediately
after `{% block content %}` opens, with three `<li>`s carrying
`data-step-id`. Use a Jinja conditional on `resume_asset_id` to set
`aria-current="step"` on the upload step (when unset) or the preferences
step (when set).

- [x] **Step 2: Verify focused and broad checks**

```bash
uv run pytest tests/test_routes_onboarding.py -q
uv run pytest -q
```

## Task 3: Publish

- [x] **Step 1: Commit, push, PR, merge**

```bash
git commit -m "Add first-run wizard step indicator to onboarding"
```
