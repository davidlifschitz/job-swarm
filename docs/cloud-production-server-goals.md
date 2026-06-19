# Cloud Production Server Goals

## Production Target

The cloud server should behave like a durable operator for `ml-job-swarm`, not like an ephemeral Codex thread. It should accept explicit user intent, run bounded workflows, preserve state, expose live progress, and stop at the compliance boundary. A production cloud run can discover and score jobs, prepare application packets, and surface referral/manual-submit actions, but it must preserve manual final submit as the user-controlled final step.

The target is a productionized service with measurable runtime parity against a local Codex-driven run:

- `100%` of user-visible run stages have durable state transitions: queued, running, waiting_for_user, prepared, failed, canceled, or completed.
- `100%` of prepared applications include an input manifest, output manifest, artifact paths, source URLs, and checksums.
- `0 automated final submissions` are allowed. The service can prepare packets and open review links, but the user must complete manual final submit.
- `100%` of retrieval work must pass the source policy before network access, browser access, or queue scheduling.
- `99%` of golden-fixture local and cloud decisions must match for source acceptance, job dedupe, fit scoring buckets, and packet readiness.

## Quantitative Goals

| Area | P0 target | P1 target | How to measure |
| --- | --- | --- | --- |
| Runtime parity | `99%` golden-fixture decision match with local Codex run | `100%` match for source policy fixtures | Nightly fixture run compares cloud outputs to committed local baselines |
| Availability | `99.5%` monthly API uptime | `99.9%` monthly API uptime | Synthetic health checks every `60 seconds` |
| Health latency | `/healthz` p95 `<= 200 ms`, p99 `<= 500 ms` | `/healthz` p95 `<= 100 ms` | External probe and internal histogram |
| Queue acknowledgement | New run accepted p95 `<= 2 seconds` | p95 `<= 1 second` | API timing from request to run id |
| First visible progress | First log/progress event p95 `<= 10 seconds` | p95 `<= 5 seconds` | Event stream audit |
| Progress freshness | Running jobs emit heartbeat every `<= 15 seconds` | Stage progress every `<= 60 seconds` | Missing-heartbeat alert |
| Run cancellation | User cancel takes effect p95 `<= 10 seconds` | p95 `<= 5 seconds` | Cancel request to terminal state |
| Restart recovery | Resume queued/running state after process restart `<= 60 seconds` | `<= 30 seconds` | Chaos restart test |
| Workflow idempotency | Same run id creates `0` duplicate packets and `0` duplicate job decisions | `100%` idempotent retries | Retry test and database uniqueness checks |
| Source policy | `100%` blocked sources denied before fetch/browser work | `0` unauthorized LinkedIn or Indeed scraping attempts | Policy unit tests plus network audit |
| Manual submit boundary | `0 automated final submissions` in all environments | `100%` submit actions require user confirmation outside automation | Browser/action audit log |
| Packet readiness | `100%` prepared packets have resume PDF, source URL, decision record, and review status | Packet render p95 `<= 5 seconds` | Packet manifest validator |
| Referral matching | Refresh existing saved jobs p95 `<= 2 minutes` for `1,000 jobs` and `5,000 contacts` | Incremental refresh p95 `<= 30 seconds` | Seeded database benchmark |
| Data durability | RPO `<= 5 minutes` | RPO `<= 1 minute` | Backup timestamp and restore drill |
| Restore time | RTO `<= 15 minutes` for database plus artifacts | RTO `<= 5 minutes` | Quarterly restore exercise |
| Artifact retention | Retain manifests and prepared packets for `90 days` by default | User-configurable `30-365 days` | Retention job report |
| Observability | `100%` state transitions emit structured logs and metrics | `100%` runs have trace id across API, worker, and artifact writes | Log schema test |
| Alerting | Page/notify within `5 minutes` of P0 SLO breach | Notify within `2 minutes` | Alert replay test |
| Security | `0` secrets in logs, artifacts, or client payloads | `100%` secret scans pass in CI and release gate | Secret scanner and log sampler |
| User isolation | `100%` run, artifact, and credential reads scoped to owner | `0` cross-user access in authorization tests | Multi-user API tests |
| Cost | Idle cost `<= 3 usd/day`; marginal run cost p95 `<= 0.25 usd` | Idle cost `<= 1 usd/day` | Daily cost export tagged by service/run |
| Capacity | Sustain `10` concurrent runs and `100` queued runs | Sustain `25` concurrent runs and `500` queued runs | Load test with seeded fixtures |
| Resource bounds | Single run p95 memory `<= 2 GB`, p95 CPU `<= 2 CPU` | Long-run cap `<= 4 hours` | Worker resource metrics |
| Deployment | Rollback available `<= 5 minutes` after bad deploy | Zero-downtime deploy p95 `<= 2 minutes` | Deploy drill |

## Server Behavior Contract

1. The server acts as a state machine. Every run has a stable run id, user id, requested action, input manifest, status, timestamps, and terminal outcome.
2. The server does not rely on chat context for correctness. Every decision required to resume, audit, cancel, or explain a run is persisted before the next stage starts.
3. The server is explicit about work. It exposes live logs, progress events, current stage, last heartbeat age, artifact links, retry count, and the next required user action.
4. The server is bounded by source policy. If a source is blocked, the run records a policy-denied result and does not fetch, scrape, browse, or enqueue follow-up work for that source.
5. The server is compliance-first. It prepares application material and referral actions, but it does not click final submit, impersonate the user, bypass source terms, or hide network origin.
6. The server treats user approval as durable state. A waiting_for_user stage survives restarts and must not silently continue after deploys, retries, or worker replacement.
7. The server is reproducible. Each run records code version, container image digest, dependency lock hash, environment class, feature flags, prompt/model identity when used, and source-policy version.
8. The server is observable by default. An operator can answer within `60 seconds`: what is running, what is blocked, what failed, what it cost, which artifacts were produced, and what user action is next.
9. The server is least-privilege. Network, browser, database, artifact, and secret access are scoped to the smallest stage that needs them.
10. The server fails closed. Missing credentials, missing resume assets, ambiguous submit controls, expired sessions, policy uncertainty, or unexpected source behavior must produce a failed or waiting_for_user state, not an automated workaround.

## TDD Acceptance Plan

The cloud server should be productionized in test-first slices. Each slice starts with a failing test, confirms the failure reason, then adds the smallest implementation that makes the test pass.

| Slice | First failing test | Done when |
| --- | --- | --- |
| Run state model | Creating a run without persisted status/history fails the contract test | `100%` runs expose durable lifecycle state and timestamps |
| Runtime parity harness | Cloud fixture output differs from local baseline and fails with a clear diff | Golden fixtures reach `99%` decision parity |
| Source policy gate | A blocked source attempts network work and fails the test | `100%` blocked sources stop before fetch/browser scheduling |
| Manual submit boundary | A final-submit action can be invoked by automation and fails the test | `0 automated final submissions` across unit, API, and browser tests |
| Progress stream | A running workflow emits no heartbeat and fails the test | Heartbeat interval is `<= 15 seconds` and first progress p95 is `<= 10 seconds` |
| Idempotent retry | Replaying the same run id creates duplicate packets and fails the test | Duplicate packet/job count is `0` under retries |
| Restart recovery | Killing a worker loses queued/running state and fails the test | Recovery time is `<= 60 seconds` |
| Artifact manifest | Prepared packet missing checksum/source URL/resume path fails validation | `100%` prepared packets have complete manifests |
| Observability schema | A transition without run id, stage, duration, and trace id fails the test | `100%` transitions satisfy log schema |
| Security guard | A seeded secret appears in logs/artifacts and fails the test | Secret leakage count is `0` |
| Load target | Seeded `10` concurrent runs breach queue/progress targets and fail the test | Capacity target passes under fixture load |
| Restore drill | Restored database/artifacts miss a prepared packet and fail the test | RPO `<= 5 minutes` and RTO `<= 15 minutes` |

## Implemented Baseline

As of `2026-05-14`, the repo has a production-runtime baseline behind `/api/cloud/*`:

- `GET /healthz` exposes service, database, status, and P0 SLO target metadata for external probes.
- `GET /api/cloud/readiness` exposes operator truth: run counts, active run ids, terminal run ids, user-action run ids, database health, and SLO targets.
- `GET /api/cloud/runs` lists durable runs with ordered event histories for live operator inspection.
- `POST /api/cloud/runs` creates idempotent durable run records with user id, requested action, input manifest, trace id, code version, image digest, lock hash, environment class, feature flags, and source-policy version.
- `GET /api/cloud/runs/{run_id}` returns current lifecycle state plus ordered events.
- `POST /api/cloud/runs/{run_id}/heartbeat` records running-stage heartbeats.
- `POST /api/cloud/runs/{run_id}/cancel` records operator cancellation as a terminal state.
- `POST /api/cloud/runs/{run_id}/sources/evaluate` classifies source URLs before work is scheduled and records blocked/manual-review outcomes as waiting_for_user.
- `POST /api/cloud/runs/{run_id}/application-packets/prepared` requires packet manifests with resume PDF, source URL, decision id, artifact checksums, and review status before marking a run prepared.
- `POST /api/cloud/runs/{run_id}/final-submit` returns manual-submit instructions and returns `409` for automation attempts, preserving `0 automated final submissions`.
- Runtime helpers compare local/cloud golden decisions for the `99%` P0 parity target, preserve state across SQLite reconnects, and redact sensitive values from client-visible run payloads and event payloads.
- `POST /api/cloud/worker/run-next` claims the oldest queued cloud run and executes the local workflow through persisted cloud stages.
- `POST /api/cloud/workflows/continue` creates an idempotent `continue_local_workflow` run and executes it immediately for cloud-thread style handoff.
- Runs with `source_ids` refresh approved public ATS/employer sources through the existing adapter registry and store refresh results in the run output manifest.
- Runs with `target_profile_id` execute rules-first matching, or LLM fit review when a fit client is configured and `review_jobs_with_llm` is set.
- Runs with `prepare_packets: true` create real `application_packets` records using the existing packet-prep path, record cloud packet manifests with resume path, source URL, decision id, and checksums, then stop at manual final submit.
- Runs with restricted explicit `sources` move to waiting_for_user before network work is scheduled.
- Worker failures persist as failed runs with `cloud_worker_failed` diagnostics and a `run_failed` event.
- `ml-job-swarm-cloud-worker --db-path <path> --max-runs <n>` runs a queue-draining worker process for cloud deployments that create queued runs separately.

## Non-Goals For V1

- No autonomous final submission.
- No hidden scraping through proxy sources to bypass blocked source policy.
- No dependence on a single long-lived browser session for correctness.
- No production behavior that only works because a Codex thread kept unstated context in memory.
- No unbounded background loops without run ids, budgets, cancellation, and audit logs.

## Operator Readiness Checklist

- A new operator can start, observe, cancel, retry, and audit a run using documented commands in `<= 15 minutes`.
- A user can see current stage, latest progress, next action, and prepared artifacts in `<= 2 clicks` from the dashboard.
- A failed run includes a stable error code, user-safe message, internal diagnostic id, and reproduction bundle in `100%` of P0 workflows.
- A deploy cannot proceed unless spec tests, source policy tests, packet readiness tests, and a fixture cloud parity check pass.
