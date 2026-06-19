# Safe External Links Plan

**Goal:** Add `rel="noopener noreferrer" target="_blank"` to every
user-facing external link.

**Architecture:** Pure template change. Two templates, four anchor tags.

**Tech Stack:** Jinja, pytest.

---

## Files

- Modify: `ml_job_swarm/web/templates/job_detail.html`
- Modify: `ml_job_swarm/web/templates/saved_jobs.html`
- Modify: `tests/test_routes_onboarding.py`

## Task 1: Tests First

- [x] **Step 1: Add failing tests**

In `tests/test_routes_onboarding.py`:

- Add `test_job_detail_external_links_are_safe` that seeds a job with
  `apply_url` and `source_url`, GETs `/jobs/{id}?target_profile_id=...`,
  and asserts the response contains `rel="noopener noreferrer"` and
  `target="_blank"` near each of the two URLs.
- Add `test_saved_jobs_external_links_are_safe` that seeds a saved job
  with both URLs, GETs `/dashboard/saved?target_profile_id=...`, and
  asserts the same attributes on the apply and source links.

- [x] **Step 2: Verify red**

```bash
uv run pytest tests/test_routes_onboarding.py -q
```

## Task 2: Implementation

- [x] **Step 1: Update job_detail.html**

Change line 20 to:
`<a href="{{ job.apply_url }}" rel="noopener noreferrer" target="_blank">{{ job.apply_url }}</a>`

Change line 21 to:
`<a href="{{ job.source_url }}" rel="noopener noreferrer" target="_blank">{{ job.source_url }}</a>`

- [x] **Step 2: Update saved_jobs.html**

Change line 50 to:
`{% if job.apply_url %}<a href="{{ job.apply_url }}" rel="noopener noreferrer" target="_blank">Apply</a>{% endif %}`

Change line 51 to:
`<a href="{{ job.source_url }}" rel="noopener noreferrer" target="_blank">Source</a>`

- [x] **Step 3: Verify focused and broad checks**

```bash
uv run pytest tests/test_routes_onboarding.py -q
uv run pytest -q
```

## Task 3: Publish

- [x] **Step 1: Commit, push, PR, merge**

```bash
git commit -m "Mark external job links rel=noopener noreferrer"
```
