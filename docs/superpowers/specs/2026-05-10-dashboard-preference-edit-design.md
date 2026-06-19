# Dashboard Preference Edit Design

## Goal

Let users update target preferences after onboarding and force a fresh rematch.

## Scope

Users can create a target profile during onboarding, but they cannot change the
target role, level, location, work mode, or company stage from the web UI. This
slice adds an inline dashboard preference form that updates the existing target
profile version using the existing `update_preferences()` behavior.

This does not add background matching, new LLM calls, authenticated scraping,
cookies, CAPTCHA bypass, LinkedIn, Indeed, or final submit automation.

## Behavior

- Dashboard profile summary shows an editable target preferences form.
- Posting the form updates the target profile, bumps its version, and redirects
  back to the dashboard.
- Old fit reviews are naturally hidden because dashboard results only use the
  current profile version.
- Missing required preference fields return a controlled 400.

## Tests

- Dashboard route test verifies the edit form is rendered with current target
  values.
- Route test posts updated preferences and verifies profile version increments
  and old reviewed matches are no longer displayed.

## Review Gates

Run goal-review and test-quality-review. Run focused dashboard route tests and
the full suite.
