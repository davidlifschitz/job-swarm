# Cloud runtime parity fixtures

Golden baseline decisions for comparing local and cloud runtime behavior.

## Files

| File | Purpose |
| --- | --- |
| `source_policy_cases.json` | URLs exercised by the source-policy gate |
| `fit_bucket_cases.json` | Rules-first fit bucket mapping and golden profile reference |
| `baseline_decisions.json` | Committed local baseline `{id, decision}` records |

## Decision ids

- `source-policy:<slug>` — `classify_source_url` mode: `allowed`, `blocked`, or `manual_link`
- `fit-bucket:<external_id>` — rules-first bucket: `strong`, `moderate`, or `weak`

Fit bucket mapping:

| Rules outcome | Bucket |
| --- | --- |
| `pass` | `strong` |
| `soft_pass` | `moderate` |
| `reject` | `weak` |

## Parity gate

`compare_runtime_parity` from `ml_job_swarm.cloud_runtime` compares the committed
baseline to decisions recomputed from these fixtures. The P0 target is **99%** match.

Run the gate:

```bash
pytest tests/test_cloud_runtime_parity_fixtures.py -q
# or
./scripts/run-cloud-parity-check.sh
```

## Updating the baseline

When source policy or rules-first fit behavior changes intentionally:

1. Recompute decisions with the current code.
2. Update `baseline_decisions.json`.
3. Confirm `tests/test_cloud_runtime_parity_fixtures.py` passes.
