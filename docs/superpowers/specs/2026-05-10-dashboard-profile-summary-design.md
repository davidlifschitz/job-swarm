# Dashboard Profile Summary Design

Branch: `codex/dashboard-profile-summary`

## Goal

Show the active target profile and resume keyword summary on the dashboard so the user can see what the matcher is using.

## Context

The first-principles V1 spec calls for a persistent dashboard with profile, resume keywords, preferences, and catalog status. The current dashboard shows job matches and resume workspace content, but it does not summarize the active profile inputs in one scannable panel.

## V1 Scope

- Add an active profile summary to `/dashboard?target_profile_id=...`.
- Show profile name, version, desired titles, levels, locations, remote modes, company stages, and resume filename.
- Show top resume keywords from the latest parse run for the profile's resume asset.
- Hide the panel when onboarding is required.
- Do not expose raw resume text, prompts, provider metadata, cookies, tokens, or browser profile data.

## Out Of Scope

- No preference editing in this slice.
- No LLM calls.
- No refresh or re-score action.
- No catalog timestamp if no ingestion run exists; that can be a follow-up slice.

## Data And Safety

The panel reads local SQLite only. Keywords are short extracted terms already stored in `resume_keywords`; full resume sections remain in the existing resume workspace. All output is Jinja-escaped.

## TDD And Review Gates

- Start with route tests for populated profile summary, latest-parse keyword selection, empty keyword state, and onboarding hiding.
- Confirm tests fail before implementation.
- Implement helper and dashboard template panel.
- Run focused tests, full suite, and browser smoke.
- Run goal-review before publishing.
