#!/usr/bin/env bash
# Pre-deploy checks for Railway hosted Tier 2 (Phase A SQLite or Phase B Postgres).
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

IMAGE="${ML_JOB_SWARM_IMAGE:-ml-job-swarm:preflight}"
PORT="${PREFLIGHT_PORT:-18080}"
DATA_DIR="${PREFLIGHT_DATA_DIR:-/tmp/ml-job-swarm-preflight-data}"
JWT_SECRET="${PREFLIGHT_JWT_SECRET:-test-jwt-secret-for-hosted-auth-32b}"

echo "==> Building Docker image (${IMAGE})"
docker build -t "${IMAGE}" .

echo "==> Starting container on port ${PORT}"
mkdir -p "${DATA_DIR}"
container_id="$(
  docker run -d --rm \
    -p "${PORT}:${PORT}" \
    -e PORT="${PORT}" \
    -e ML_JOB_SWARM_DATA_DIR=/data \
    -e SUPABASE_URL=https://example.supabase.co \
    -e SUPABASE_ANON_KEY=preflight-anon-key \
    -e SUPABASE_JWT_SECRET="${JWT_SECRET}" \
    -v "${DATA_DIR}:/data" \
    "${IMAGE}"
)"

pg_id=""
pg_container_id=""
cleanup() {
  docker stop "${pg_container_id}" >/dev/null 2>&1 || true
  docker stop "${pg_id}" >/dev/null 2>&1 || true
  docker stop "${container_id}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

base_url="http://127.0.0.1:${PORT}"
deadline=$((SECONDS + 60))
until curl -fsS "${base_url}/healthz" >/dev/null 2>&1; do
  if (( SECONDS >= deadline )); then
    echo "Container failed to become healthy within 60s" >&2
    docker logs "${container_id}" >&2 || true
    exit 1
  fi
  sleep 1
done

echo "==> Running hosted smoke checks (auth gate enabled)"
./scripts/smoke-hosted.sh "${base_url}"

export PREFLIGHT_JWT_SECRET="${JWT_SECRET}"
token="$(
  uv run python - <<'PY'
import jwt
import os
import time

secret = os.environ["PREFLIGHT_JWT_SECRET"]
print(
    jwt.encode(
        {"sub": "preflight-user", "aud": "authenticated", "exp": int(time.time()) + 3600},
        secret,
        algorithm="HS256",
    )
)
PY
)"
echo "==> Running hosted smoke checks (authenticated)"
./scripts/smoke-hosted.sh "${base_url}" "${token}"

if [[ "${PREFLIGHT_POSTGRES:-}" == "1" ]]; then
  echo "==> Starting Postgres sidecar for Phase B preflight"
  pg_id="$(docker run -d --rm -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=jobs -p 55431:5432 postgres:16-alpine)"
  deadline=$((SECONDS + 30))
  until docker exec "${pg_id}" pg_isready -U postgres >/dev/null 2>&1; do
    if (( SECONDS >= deadline )); then
      echo "Postgres sidecar failed to start" >&2
      exit 1
    fi
    sleep 1
  done
  pg_url="postgresql://postgres:postgres@host.docker.internal:55431/jobs"
  pg_container_id="$(
    docker run -d --rm \
      -p "$((PORT + 1)):$((PORT + 1))" \
      -e PORT="$((PORT + 1))" \
      -e DATABASE_URL="${pg_url}" \
      -e SUPABASE_URL=https://example.supabase.co \
      -e SUPABASE_SERVICE_ROLE_KEY=preflight-service-role \
      -e ML_JOB_SWARM_RESUME_STORAGE_BUCKET=resume-assets \
      --add-host=host.docker.internal:host-gateway \
      "${IMAGE}"
  )"
  pg_base_url="http://127.0.0.1:$((PORT + 1))"
  deadline=$((SECONDS + 60))
  until curl -fsS "${pg_base_url}/healthz" >/dev/null 2>&1; do
    if (( SECONDS >= deadline )); then
      echo "Postgres preflight container failed to become healthy" >&2
      docker logs "${pg_container_id}" >&2 || true
      exit 1
    fi
    sleep 1
  done
  echo "==> Running Postgres cutover smoke (expect postgresql + supabase storage mode)"
  ML_JOB_SWARM_EXPECT_POSTGRES=1 ./scripts/smoke-postgres-cutover.sh "${pg_base_url}" "${token}"
fi

echo
echo "Preflight passed. Next steps for Railway go-live:"
echo "  1. railway login"
echo "  2. Create Supabase project → set SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_JWT_SECRET"
echo "  3. Railway → deploy davidlifschitz/job-swarm, mount volume at /data"
echo "  4. Copy env vars from .env.hosted.example"
echo "  5. ./scripts/smoke-hosted.sh https://<your-app>.up.railway.app [ACCESS_TOKEN]"
echo
echo "See docs/tier2-hosted-web.md for the full checklist."