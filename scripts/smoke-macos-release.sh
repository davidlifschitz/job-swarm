#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_PATH="$(cd "$(dirname "${1:-${ROOT_DIR}/macos/dist/MLJobSwarm.app}")" && pwd)/$(basename "${1:-${ROOT_DIR}/macos/dist/MLJobSwarm.app}")"
SMOKE_DB="$(mktemp -d)/jobs.db"
PORT="$(python3 - <<'PY'
import socket
s = socket.socket()
s.bind(("", 0))
print(s.getsockname()[1])
s.close()
PY
)"
HEALTH_URL="http://127.0.0.1:${PORT}/api/v1/health"

cleanup() {
  if [[ -n "${BACKEND_PID:-}" ]]; then
    kill "${BACKEND_PID}" 2>/dev/null || true
    wait "${BACKEND_PID}" 2>/dev/null || true
  fi
}
trap cleanup EXIT

if [[ ! -x "${APP_PATH}/Contents/MacOS/MLJobSwarm" ]]; then
  echo "App bundle missing executable: ${APP_PATH}" >&2
  exit 1
fi

BACKEND="${APP_PATH}/Contents/Resources/backend"
VENV_PY="${BACKEND}/.venv/bin/python3"
if [[ ! -x "${VENV_PY}" ]]; then
  VENV_PY="${BACKEND}/.venv/bin/python"
fi
if [[ ! -x "${VENV_PY}" ]]; then
  echo "Bundled backend venv missing python: ${BACKEND}/.venv/bin" >&2
  exit 1
fi

echo "Smoke: bundled backend health on port ${PORT}"
(
  cd "${BACKEND}"
  ML_JOB_SWARM_DB_PATH="${SMOKE_DB}" \
  ML_JOB_SWARM_SEED_COMPANIES="${BACKEND}/data/seed_companies.json" \
  "${VENV_PY}" -m uvicorn 'ml_job_swarm.app:create_app_from_env' \
    --factory --host 127.0.0.1 --port "${PORT}"
) &
BACKEND_PID=$!

deadline=$((SECONDS + 60))
until curl -fsS "${HEALTH_URL}" >/dev/null 2>&1; do
  if (( SECONDS > deadline )); then
    echo "Timed out waiting for ${HEALTH_URL}" >&2
    exit 1
  fi
  if ! kill -0 "${BACKEND_PID}" 2>/dev/null; then
    echo "Backend process exited before health check passed." >&2
    exit 1
  fi
  sleep 1
done

echo "Smoke: seed catalog imported"
LOADED="$(curl -fsS "${HEALTH_URL}" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status',''))")"
test "${LOADED}" = "ok"

echo "Smoke: swift binary launches (--help not applicable; verify codesign)"
codesign -dv "${APP_PATH}" >/dev/null 2>&1

echo "macOS release smoke passed."