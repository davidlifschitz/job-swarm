# Public Ashby Adapter Plan

Spec: `docs/superpowers/specs/2026-05-10-public-ashby-adapter-design.md`

## Goal

Add a tested public Ashby adapter to improve seeded catalog refresh coverage.

## Ownership

- Controller-owned files:
  - `ml_job_swarm/adapters.py`
  - `tests/test_adapters_public_ats.py`

## TDD Steps

1. Add Ashby adapter happy-path test:
   - source `https://jobs.ashbyhq.com/example`
   - expected API URL
   - parse title, department/team, location, workplace type, employment type, description, apply/source URL.
2. Add test that unlisted Ashby jobs are skipped.
3. Add test that malformed Ashby payload raises `RefreshError`.
4. Add registry test for `ashby`.
5. Add default fetcher header test for browser-compatible public ATS requests.
6. Implement adapter and helper functions.

## Verification

Focused:

```bash
uv run pytest tests/test_adapters_public_ats.py -q
```

Full:

```bash
uv run pytest
```

Runtime smoke:

```bash
uv run python - <<'PY'
from ml_job_swarm import adapters
payload = adapters._default_fetch_json(
    "https://api.ashbyhq.com/posting-api/job-board/openai?includeCompensation=false"
)
assert isinstance(payload.get("jobs"), list)
PY
```

## Review Gates

- `goal-review`: confirm this improves real job refresh without adding prohibited scraping.
- `test-quality-review`: confirm tests prove URL shape, parsing, filtering, and registry coverage with mocked fetchers.
