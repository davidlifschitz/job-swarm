# Saved Jobs Export Design

Status: approved-for-implementation follow-up slice
Date: 2026-05-09
Branch: `codex/saved-jobs-export`

## Goal

Let the user export their local saved-job shortlist as a CSV from the dashboard without adding an application workflow or sending private resume data anywhere.

## Product Fit

The dashboard now supports saved and hidden decisions. Exporting saved jobs is the next smallest local-first utility: it turns fit review into a portable shortlist while keeping V1 away from applications, outreach, and external sync.

## V1 Scope

- Add a CSV export route for saved jobs by `target_profile_id`.
- Include only jobs with `job_decisions.decision = 'saved'`.
- Use the latest fit review for the current profile version.
- Include company, title, fit score, label, recommendation, apply URL, source URL, and decision timestamp.
- Add a dashboard link when a target profile is active.

## Non-Goals

- No application submission.
- No resume export.
- No tailored resume generation.
- No external sync to spreadsheets, email, LinkedIn, Indeed, or ATS sites.
- No hidden or unmarked jobs in the saved export.

## Privacy Rules

- Do not include raw resume text, parsed resume sections, prompt text, cookies, tokens, browser profile data, or private LLM request details.
- The export is generated locally from SQLite.

## Tests

- helper returns only saved jobs for the requested target profile
- hidden and unmarked jobs are excluded
- route requires `target_profile_id`
- CSV output contains safe shortlist fields and excludes private resume text
- dashboard exposes the export link for active profiles

## V2 Options

- XLSX export
- saved-job notes export
- application packet export after manual-submit workflow exists
