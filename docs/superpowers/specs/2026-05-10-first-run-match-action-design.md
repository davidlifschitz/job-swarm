# First-Run Match Action Design

## Goal

Bridge onboarding into real grouped job results with one explicit user action.

## Scope

After a user uploads a resume and saves preferences, the dashboard can still
show "No current matches" if public sources have not been refreshed or jobs have
not been fit-reviewed. This slice adds a dashboard "Find matches" action that
refreshes reviewed public sources, runs the fit gate with explicit LLM consent,
and redirects back to grouped results with counts.

This does not add background scheduling, authenticated scraping, cookies,
CAPTCHA bypass, hidden browser sessions, LinkedIn, Indeed, or final submit
automation.

## Behavior

- `/dashboard/find-matches` requires `target_profile_id` and explicit LLM
  consent.
- The route requires a configured fit-gate client before refreshing sources.
- It refreshes reviewed sources supported by the public adapter registry.
- It runs fit review for the target profile after refresh.
- It redirects to `/dashboard` with match-run counts:
  - match status
  - sources refreshed
  - sources skipped
  - jobs seen
  - reviews created
  - failures
  - blocked
- The dashboard renders a small match-run summary from those query params.

## Tests

- Route test seeds one reviewed source, a target profile, fake public adapter,
  and fake fit client. Posting the action returns a redirect with counts and the
  redirected dashboard shows the grouped job.
- Dashboard HTML test verifies the first-run "Find matches" action is visible
  when a profile exists but no current matches are shown.

## Review Gates

Run goal-review and test-quality-review. Run focused dashboard route tests and
the full suite.
