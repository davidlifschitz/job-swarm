# Dashboard Unreviewed Jobs Design

## Goal

Show real refreshed jobs on the dashboard even before the current target profile has fit reviews for them.

## Why This Matters

Public source refresh can now ingest real jobs without OpenRouter. If those jobs are not reviewed yet, the dashboard can still look empty because the main match table is fit-review driven. The user should see that jobs exist and are waiting for review, rather than thinking refresh did nothing.

## V1 Scope

- Add a dashboard section for open jobs missing a fit review for the current target profile version.
- Show company, title, location, and a link to the local job detail page.
- Limit the section to a small recent set to keep the dashboard usable.
- Keep the reviewed match table unchanged.
- Do not run rules or LLM review automatically.

## Safety Boundaries

- No private data leaves the machine.
- No external fetch happens while rendering the waiting list.
- The section must label these as waiting for review, not as matches.

## Acceptance Criteria

- Jobs created by public refresh appear under `Jobs waiting for fit review` before scoring.
- Jobs with a current fit review do not appear in the waiting list.
- The dashboard still shows current reviewed matches as before.
- Preference version changes can make previously reviewed jobs wait for re-review.

## Review Gates

- `goal-review`: confirm this makes real refreshed jobs visible without mislabeling them as matches.
- `test-quality-review`: confirm route tests cover unreviewed, reviewed, and profile-version behavior.
