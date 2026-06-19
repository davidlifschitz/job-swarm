# Job Decision Workspace Design

Status: approved-for-implementation follow-up slice
Date: 2026-05-09
Branch: `codex/job-decision-workspace`

## Goal

Let a user make lightweight local decisions on matched jobs: save jobs worth pursuing, hide jobs they do not want to see in the main list, and undo those decisions without starting an application workflow.

## Product Fit

The V1 dashboard already groups matches by company and hides mismatch-risk jobs by default. The missing first-principles step is triage: after fit review, the user needs a durable local shortlist and a way to suppress noise.

## V1 Scope

- Store saved/hidden decisions per `target_profile_id` and `job_id`.
- Show saved jobs in the normal company list with a visible marker.
- Move hidden jobs out of the normal visible/mismatch lists into a separate collapsed section under the company.
- Allow clearing a saved or hidden decision.
- Keep all decisions local in SQLite.

## Non-Goals

- No application workflow.
- No outreach, CRM, reminders, or notifications.
- No sync to external job boards.
- No Cloudflare auth or hosted multi-user permissions.
- No LLM call when a user saves or hides a job.

## Data Contract

Create `job_decisions`:

- `job_id`
- `target_profile_id`
- `decision`: `saved` or `hidden`
- `notes`: optional local note for later expansion
- timestamps
- unique key on `(job_id, target_profile_id)`

The decision is tied to the target profile because a job can be hidden for one search profile and still be relevant for another.

## Dashboard UI

Visible fit rows show:

- title
- fit label
- score
- recommendation
- decision state
- Save, Hide, or Clear controls

Each company can also show:

- mismatch-risk jobs under the existing collapsed mismatch section
- hidden-by-user jobs under a separate collapsed section

## Safety and Privacy

- Decisions do not store resume text, prompt text, cookies, tokens, or browser profile data.
- Save/hide actions are local POSTs only.
- Hidden jobs are not deleted; they remain auditable and reversible.

## Tests

- schema creates `job_decisions`
- helper upserts saved/hidden decisions and clears them
- invalid decisions are rejected
- dashboard marks saved jobs
- hidden jobs move out of visible results and into a hidden section
- route actions persist decisions and redirect back to the same profile dashboard

## V2 Options

- local notes editor
- shortlist export
- status pipeline for prepared/applied/manual-submit later
- reminders after application workflow exists
