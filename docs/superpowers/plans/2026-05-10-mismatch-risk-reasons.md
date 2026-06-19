# Mismatch-Risk Reasons Inline Plan

**Goal:** Render `JobFitResult.risks` in the dashboard mismatch-risks
list so users see WHY each job is flagged.

**Architecture:** Pure template change in `dashboard.html`.

**Tech Stack:** Jinja, pytest.

---

## Files

- Modify: `ml_job_swarm/web/templates/dashboard.html`
- Modify: `tests/test_routes_onboarding.py`

## Task 1: Tests First

- [x] **Step 1: Add failing test**

In `tests/test_routes_onboarding.py` add `test_dashboard_mismatch_risks_show_risk_reasons` that seeds a job with `label="Mismatch risk"`, `risks=["role_needs_review", "location_mismatch"]`, GETs the dashboard, and asserts the response contains both risk strings inside a `class="job-risks"` element.

(Note: existing seed helper `_seed_reviewed_job` writes `risks_json='[]'`. The new test will need to pass `risks_json` directly via a small helper or by patching the row.)

- [x] **Step 2: Verify red**

```bash
uv run pytest tests/test_routes_onboarding.py -q
```

## Task 2: Implementation

- [x] **Step 1: Update dashboard template**

In `dashboard.html` line 144, replace:

```jinja
<li><a href=...>{{ job.title }}</a> - {{ job.fit_score }}</li>
```

with markup that adds:

```jinja
{% if job.risks %}<span class="job-risks">{{ job.risks|join(", ") }}</span>{% endif %}
```

after the score.

- [x] **Step 2: Verify focused and broad checks**

```bash
uv run pytest tests/test_routes_onboarding.py -q
uv run pytest -q
```

## Task 3: Publish

- [x] **Step 1: Commit, push, PR, merge**

```bash
git commit -m "Show mismatch-risk reasons inline on dashboard"
```
