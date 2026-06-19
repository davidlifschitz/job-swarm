#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

export ML_JOB_SWARM_DATA_DIR="${ML_JOB_SWARM_DATA_DIR:-/data}"
export ML_JOB_SWARM_DB_PATH="${ML_JOB_SWARM_DB_PATH:-${ML_JOB_SWARM_DATA_DIR}/jobs.db}"
export ML_JOB_SWARM_RESUME_ASSET_DIR="${ML_JOB_SWARM_RESUME_ASSET_DIR:-${ML_JOB_SWARM_DATA_DIR}/resume-assets}"
export ML_JOB_SWARM_SEED_COMPANIES="${ML_JOB_SWARM_SEED_COMPANIES:-data/seed_companies.json}"

mkdir -p "$(dirname "${ML_JOB_SWARM_DB_PATH}")" "${ML_JOB_SWARM_RESUME_ASSET_DIR}"

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8080}"

exec uv run uvicorn "ml_job_swarm.app:create_app_from_env" \
  --factory \
  --host "${HOST}" \
  --port "${PORT}"