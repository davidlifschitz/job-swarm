#!/usr/bin/env bash
# Phase B production cutover: migrate volume SQLite → Supabase Postgres and verify.
#
# Prerequisites:
#   - Supabase migrations applied (supabase db push --linked)
#   - resume-assets Storage bucket created (private)
#   - Railway web has DATABASE_URL, SUPABASE_SERVICE_ROLE_KEY, ML_JOB_SWARM_RESUME_STORAGE_BUCKET
#
# Usage:
#   ./scripts/railway-cutover.sh --check-env
#   ML_JOB_SWARM_SOURCE_DB=/path/to/jobs.db ./scripts/railway-cutover.sh --dry-run
#   ML_JOB_SWARM_SOURCE_DB=/path/to/jobs.db ./scripts/railway-cutover.sh
#   ./scripts/railway-cutover.sh --smoke-only https://your-app.up.railway.app [ACCESS_TOKEN]
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

SMOKE_ONLY=0
DRY_RUN=0
CHECK_ENV=0
BASE_URL=""
TOKEN="${ML_JOB_SWARM_ACCESS_TOKEN:-}"

resolve_source_db() {
  echo "${ML_JOB_SWARM_SOURCE_DB:-${ML_JOB_SWARM_DB_PATH:-}}"
}

run_check_env() {
  local source_db
  source_db="$(resolve_source_db)"

  echo "Railway cutover — environment check"
  echo
  echo "Dry-run (--dry-run):"
  echo "  Required: ML_JOB_SWARM_SOURCE_DB or ML_JOB_SWARM_DB_PATH → existing SQLite export (jobs.db)"
  echo "  Optional: ML_JOB_SWARM_RESUME_ASSET_DIR"
  echo
  echo "Live cutover:"
  echo "  Required: DATABASE_URL (Supabase Settings → Database → session pooler URI)"
  echo "  Required: ML_JOB_SWARM_SOURCE_DB or ML_JOB_SWARM_DB_PATH → existing SQLite export (jobs.db)"
  echo "  Optional: ML_JOB_SWARM_RESUME_ASSET_DIR"
  echo

  local dry_run_ok=0
  local live_missing=()

  if [[ -n "${source_db}" && -f "${source_db}" ]]; then
    echo "Dry-run: OK (source: ${source_db})"
    dry_run_ok=1
  else
    echo "Dry-run: BLOCKED"
    if [[ -z "${source_db}" ]]; then
      echo "  - ML_JOB_SWARM_SOURCE_DB (or ML_JOB_SWARM_DB_PATH) is not set"
    else
      echo "  - Source DB not found: ${source_db}"
    fi
  fi

  if [[ -z "${DATABASE_URL:-}" ]]; then
    live_missing+=("DATABASE_URL (Supabase Settings → Database → session pooler URI)")
  fi
  if [[ -z "${source_db}" ]]; then
    live_missing+=("ML_JOB_SWARM_SOURCE_DB (or ML_JOB_SWARM_DB_PATH) — path to hosted SQLite export")
  elif [[ ! -f "${source_db}" ]]; then
    live_missing+=("ML_JOB_SWARM_SOURCE_DB — file not found: ${source_db}")
  fi

  if [[ ${#live_missing[@]} -eq 0 ]]; then
    echo "Live cutover: OK"
    echo
    echo "Environment OK for dry-run and live cutover."
    return 0
  fi

  echo "Live cutover: BLOCKED"
  for item in "${live_missing[@]}"; do
    echo "  - ${item}"
  done
  echo
  echo "Live cutover blocked — set missing variables above." >&2
  if [[ ${dry_run_ok} -eq 1 ]]; then
    echo "Dry-run prerequisites are met; run with --dry-run for offline validation." >&2
    return 0
  fi
  return 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --check-env) CHECK_ENV=1 ;;
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

if [[ "${CHECK_ENV}" -eq 1 ]]; then
  run_check_env
  exit $?
fi

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

SOURCE_DB="$(resolve_source_db)"
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