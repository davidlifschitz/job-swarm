#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

SOURCE_DB="${ML_JOB_SWARM_SOURCE_DB:-${ML_JOB_SWARM_DB_PATH:-${ML_JOB_SWARM_DATA_DIR:-/data}/jobs.db}}"
RESUME_DIR="${ML_JOB_SWARM_RESUME_ASSET_DIR:-${ML_JOB_SWARM_DATA_DIR:-/data}/resume-assets}"

ARGS=(migrate-hosted --source-db "${SOURCE_DB}" --resume-asset-dir "${RESUME_DIR}")
if [[ "${ML_JOB_SWARM_MIGRATE_DRY_RUN:-}" == "1" ]]; then
  ARGS+=(--dry-run)
fi

exec uv run ml-job-swarm "${ARGS[@]}" "$@"