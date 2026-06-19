# Source Refresh Support Status Design

## Goal

Make source health tell the operator which rows can actually be refreshed with
the current adapter registry before they run any refresh action.

## Scope

V1 adds per-row refresh support status to `/admin/sources`. Supported enabled
sources keep the per-source `Refresh` button. Unsupported enabled sources show
`Unsupported` and do not render a per-source refresh button. Disabled sources
keep `Enable`.

This does not add new adapters, browser scraping, authenticated scraping,
cookies, CAPTCHA bypass, LinkedIn, Indeed, or final submit automation.

## Behavior

- `_source_health_rows` receives the app's supported source types.
- Each row gets `adapter_status`:
  - `ready` when enabled and source type is registered.
  - `unsupported` when enabled but source type is not registered.
  - `disabled` when disabled, regardless of source type.
- Each row gets a short `adapter_status_label` for the table.
- The table displays a compact `Support` column.
- Unsupported rows show `No adapter` and still allow `Disable`, but not
  `Refresh`.

## Tests

- Supported source rows show `Ready` and the per-source refresh form.
- Unsupported source rows show `No adapter` and do not show the per-source
  refresh form.
- Disabled rows show `Disabled` and keep the `Enable` action.

## Review Gates

Run goal-review and test-quality-review. Run focused admin route tests, a browser
smoke on seeded source health, and the full test suite.
