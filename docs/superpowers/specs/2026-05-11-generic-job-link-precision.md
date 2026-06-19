# Generic Job Link Precision

## Goal

Prevent the generic careers-page fallback from ingesting index, facet, language, or navigation links as job postings while preserving real same-domain public job detail links.

## Problem

Some public careers pages expose index paths such as `/jobs/locations/bellevue`, `/jobs/categories/engineering`, `/careers/list`, or unresolved template links like `/jobs/{{assessmentUrl}}`. The fallback same-domain link extractor previously treated these as jobs because the path contained a careers/jobs marker and the anchor text was non-generic.

That can turn location names, departments, teams, or languages into fake job rows. A real job search product must prefer missing a weak heuristic match over showing non-jobs as open roles.

## V1 Behavior

- Keep extracting direct same-domain job detail links such as `/careers/software-engineer-ai`.
- Ignore index/facet paths for locations, categories, departments, teams, filters, and listing pages.
- Ignore unresolved template placeholders in titles or paths.
- Do not add browser automation, hidden sessions, cookies, CAPTCHA handling, or aggregator scraping.

## Review Gates

- `goal-review`: passes if the guard improves real-world job quality without expanding scraping scope.
- `test-quality-review`: passes if tests prove both the false-positive block and the preserved real job-detail behavior.
