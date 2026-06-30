#!/usr/bin/env bash
# Phase B production cutover: migrate volume SQLite → Supabase Postgres and verify.
#
# Prerequisites:
#   - Supabase migrations applied (supabase db push --linked)
#   - resume-assets Storage bucket created (private)
#   - Railway web has DATABASE_URL, SUPABASE_SERVICE_ROLE_KEY, ML_JOB_SWARM_RESUME_STORAGE_BUCKET
#
# Usage:
#   ML_JOB_SWARM_SOURCE_DB=/path/to/jobs.db ./scripts/railway-cutover.sh --dry-run
#   ML_JOB_SWARM_SOURCE_DB=/path/to/jobs.db ./scripts/railway-cutover.sh
#   ./scripts/railway-cutover.sh --smoke-only https://your-app.up.railway.app [ACCESS_TOKEN]
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

SMOKE_ONLY=0
DRY_RUN=0
BASE_URL=""
TOKEN="${ML_JOB_SWARM_ACCESS_TOKEN:-}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=1 ;;
    --smoke-only)
      SMOKE_ONLY=1
      BASE_URL="${2:-}"
      TOKEN="${3:-}"
      shift 2
      ;;
    -h|--help)
      sed -n '2,14p' "$0"
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 1
      ;;
  esac
  shift
done

if [[ "${SMOKE_ONLY}" -eq 1 ]]; then
  [[ -n "${BASE_URL}" ]] || {
    echo "Usage: $0 --smoke-only <base-url> [bearer-token]" >&2
    exit 1
  }
  ML_JOB_SWARM_EXPECT_POSTGRES=1 ./scripts/smoke-postgres-cutover.sh "${BASE_URL}" "${TOKEN}"
  echo "Postgres cutover smoke passed for ${BASE_URL}"
  exit 0
fi

if [[ "${DRY_RUN}" -eq 0 && -z "${DATABASE_URL:-}" ]]; then
  echo "DATABASE_URL is required for live migration." >&2
  echo "Set it from Supabase Settings → Database → Connection string (session pooler)." >&2
  echo "For offline validation only, pass --dry-run (no DATABASE_URL needed)." >&2
  exit 1
fi

SOURCE_DB="${ML_JOB_SWARM_SOURCE_DB:-${ML_JOB_SWARM_DB_PATH:-}}"
RESUME_DIR="${ML_JOB_SWARM_RESUME_ASSET_DIR:-}"
if [[ -z "${SOURCE_DB}" || ! -f "${SOURCE_DB}" ]]; then
  echo "ML_JOB_SWARM_SOURCE_DB must point at the hosted SQLite export (jobs.db)." >&2
  exit 1
fi

ARGS=(migrate-hosted --source-db "${SOURCE_DB}")
if [[ -n "${RESUME_DIR}" ]]; then
  ARGS+=(--resume-asset-dir "${RESUME_DIR}")
fi
if [[ "${DRY_RUN}" -eq 1 ]]; then
  ARGS+=(--dry-run)
fi

echo "==> Running hosted migration (${ARGS[*]})"
uv run ml-job-swarm "${ARGS[@]}"

if [[ "${DRY_RUN}" -eq 1 ]]; then
  echo "Dry run complete. Set Railway DATABASE_URL + service role, redeploy, then:"
  echo "  $0 --smoke-only https://<app>.up.railway.app [ACCESS_TOKEN]"
  exit 0
fi

echo "Cutover migration complete."
echo "Redeploy Railway web + worker with Phase B env vars, then:"
echo "  $0 --smoke-only \${ML_JOB_SWARM_PUBLIC_URL:-https://<app>.up.railway.app} [ACCESS_TOKEN]"