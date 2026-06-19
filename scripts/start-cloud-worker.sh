#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

export ML_JOB_SWARM_DATA_DIR="${ML_JOB_SWARM_DATA_DIR:-/data}"
export ML_JOB_SWARM_DB_PATH="${ML_JOB_SWARM_DB_PATH:-${ML_JOB_SWARM_DATA_DIR}/jobs.db}"

if [[ -z "${DATABASE_URL:-}" ]]; then
  mkdir -p "$(dirname "${ML_JOB_SWARM_DB_PATH}")"
fi

exec uv run ml-job-swarm-cloud-worker \
  --db-path "${ML_JOB_SWARM_DB_PATH}" \
  --max-runs 0