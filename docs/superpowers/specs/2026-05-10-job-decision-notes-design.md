# Job Decision Notes Design

Status: approved-for-implementation follow-up slice
Date: 2026-05-10
Branch: `codex/job-decision-notes`

## Goal

Let users attach local notes to saved or hidden jobs and carry those notes into the saved-jobs export.

## Product Fit

The `job_decisions` table already stores `notes`, but V1 currently has no dashboard path to view or update them. Notes make the saved shortlist useful for manual follow-up without starting an application workflow.

## V1 Scope

- Show existing decision notes on dashboard job rows and hidden-job entries.
- Accept optional `notes` when saving or hiding a job.
- Preserve notes in `job_decisions`.
- Include notes in saved jobs CSV export.

## Non-Goals

- No rich text editor.
- No reminders.
- No application workflow.
- No external sync.
- No LLM-generated notes.

## Safety Rules

- Notes are local SQLite data.
- Do not send notes to OpenRouter or external services.
- CSV export remains local and includes only user-authored notes for saved jobs.

## Tests

- decision helper stores notes
- dashboard save/hide route persists notes
- dashboard renders notes for saved and hidden jobs
- saved jobs CSV includes notes

## V2 Options

- dedicated notes editor
- notes search/filter
- notes in future application packets
