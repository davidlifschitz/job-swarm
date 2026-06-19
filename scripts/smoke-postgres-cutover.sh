#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:-}"
TOKEN="${2:-}"
EXPECT_POSTGRES="${ML_JOB_SWARM_EXPECT_POSTGRES:-1}"

if [[ -z "${BASE_URL}" ]]; then
  echo "Usage: $(basename "$0") <base-url> [bearer-token]" >&2
  echo "Example: $(basename "$0") https://ml-job-swarm.up.railway.app" >&2
  exit 1
fi

BASE_URL="${BASE_URL%/}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
"${SCRIPT_DIR}/smoke-hosted.sh" "${BASE_URL}" "${TOKEN}"

echo "Checking hosted storage mode"
health="$(curl -fsS "${BASE_URL}/healthz")"
python3 - <<'PY' "${health}" "${EXPECT_POSTGRES}"
import json
import sys

payload = json.loads(sys.argv[1])
expect_postgres = sys.argv[2] == "1"
assert payload["database"] == "ok", payload
if expect_postgres:
    assert payload.get("database_backend") == "postgresql", payload
    assert payload.get("resume_storage_backend") == "supabase", payload
else:
    assert payload.get("database_backend") in {"sqlite", "postgresql"}, payload
PY

if [[ -n "${TOKEN}" ]]; then
  echo "Checking /api/cloud/readiness storage mode"
  readiness="$(curl -fsS "${BASE_URL}/api/cloud/readiness" -H "Authorization: Bearer ${TOKEN}")"
  python3 - <<'PY' "${readiness}" "${EXPECT_POSTGRES}"
import json
import sys

payload = json.loads(sys.argv[1])
expect_postgres = sys.argv[2] == "1"
if expect_postgres:
    assert payload.get("database_backend") == "postgresql", payload
    assert payload.get("resume_storage_backend") == "supabase", payload
PY
fi

echo "Postgres cutover smoke checks passed for ${BASE_URL}"