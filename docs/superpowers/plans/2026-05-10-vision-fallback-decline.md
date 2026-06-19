# Vision Fallback Decline Plan

**Goal:** Give users an explicit, recorded way to decline the vision-fallback
prompt and proceed with the partial parse.

**Architecture:** Add POST `/resume/decline-vision-fallback`; mirror the
existing `/resume/vision-fallback` shape. Add a Skip button to the panel.

**Tech Stack:** FastAPI, Jinja, SQLite, pytest.

---

## Files

- Modify: `ml_job_swarm/app.py`
- Modify: `ml_job_swarm/web/templates/onboarding.html`
- Modify: `tests/test_routes_onboarding.py`

## Task 1: Tests First

- [x] **Step 1: Add failing tests**

In `tests/test_routes_onboarding.py`:

- `test_onboarding_panel_offers_skip_vision_fallback`: GET
  `/onboarding?resume_asset_id=7&vision_fallback=needed` and assert the
  rendered HTML contains both `action="/resume/vision-fallback"` and
  `action="/resume/decline-vision-fallback"` plus a button labelled
  `Skip and use what we parsed`.
- `test_decline_vision_fallback_marks_declined_and_redirects`: Upload a
  low-confidence resume (use the same monkeypatched flow as
  `test_low_confidence_resume_upload_records_pending_vision_consent`),
  POST to `/resume/decline-vision-fallback` with the resume_asset_id,
  assert 303 to `/onboarding?resume_asset_id=1` (no
  `vision_fallback=needed`), and assert the row's
  `vision_fallback_status` is `declined`.
- `test_decline_vision_fallback_requires_pending_parse_run`: POST to
  `/resume/decline-vision-fallback` with `resume_asset_id=999` (no
  pending parse run) and assert 400.

- [x] **Step 2: Verify red**

```bash
uv run pytest tests/test_routes_onboarding.py -q
```

## Task 2: Implementation

- [x] **Step 1: Add the decline route**

In `ml_job_swarm/app.py`, add `decline_vision_fallback` next to
`consent_vision_fallback`. Look up the parse run by `resume_asset_id`
with `status='needs_vision_fallback'` and
`vision_fallback_status='pending_consent'`. If absent, return 400. Else
UPDATE `vision_fallback_status='declined'` and 303-redirect to
`/onboarding?resume_asset_id={id}`.

- [x] **Step 2: Add the Skip button**

In `onboarding.html`, inside the vision-fallback panel, add a second
form posting to `/resume/decline-vision-fallback` with the
`resume_asset_id` hidden input and a `Skip and use what we parsed`
button. Tweak the panel copy to say both options are available.

- [x] **Step 3: Verify focused and broad checks**

```bash
uv run pytest tests/test_routes_onboarding.py -q
uv run pytest -q
```

## Task 3: Publish

- [x] **Step 1: Commit, push, PR, merge**

```bash
git commit -m "Allow user to decline vision fallback and proceed"
```
