# Job Detail View Design

Branch: `codex/job-detail-view`

## Goal

Add a local job-detail page linked from grouped results so the user can inspect the full job record, fit review, and decision controls without leaving the app.

## Context

The dashboard currently shows compact rows grouped by company. That works for scanning, but it hides useful context such as description, requirements, apply URL, source URL, fit reasons, risks, and notes. V1 should let the user drill into a job before deciding whether to save or hide it.

## V1 Scope

- Add `GET /jobs/{job_id}?target_profile_id=...`.
- Require `target_profile_id` so fit review and decision state are profile-scoped.
- Render company, title, location, work mode, seniority, department, employment type, apply/source links, description, requirements, fit score, label, reasons, risks, recommendation, decision, and notes.
- Link each visible dashboard job to its detail page.
- Link mismatch-risk and hidden jobs to the same detail page.
- Reuse the existing `POST /jobs/{job_id}/decision` route from the detail page.
- Return `404` for missing jobs and `400` for missing target profile id.

## Out Of Scope

- No live job refresh from the detail page.
- No application automation.
- No LLM resume rewrite generation from this page beyond existing routes.
- No hosted auth or external sharing.

## Data And Safety

The page reads from local SQLite only. Stored job descriptions are rendered through Jinja escaping. Decision forms keep using local `job_decisions` rows and must not log private resume content.

## TDD And Review Gates

- Start with route tests for missing target profile, missing job, populated details, decision forms, and dashboard links.
- Confirm the new tests fail before implementation.
- Implement the route helper, template, and dashboard links.
- Run focused route tests, full suite, and a browser smoke for the detail page.
- Run goal-review before publishing.
