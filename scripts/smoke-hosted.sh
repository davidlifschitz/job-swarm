#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:-}"
TOKEN="${2:-}"

if [[ -z "${BASE_URL}" ]]; then
  echo "Usage: $(basename "$0") <base-url> [bearer-token]" >&2
  echo "Example: $(basename "$0") https://ml-job-swarm.up.railway.app" >&2
  exit 1
fi

BASE_URL="${BASE_URL%/}"
AUTH_HEADER=()
if [[ -n "${TOKEN}" ]]; then
  AUTH_HEADER=(-H "Authorization: Bearer ${TOKEN}")
fi

echo "Checking ${BASE_URL}/healthz"
health="$(curl -fsS "${BASE_URL}/healthz")"
echo "${health}" | python3 -c "import json,sys; d=json.load(sys.stdin); assert d['status']=='ok', d"

echo "Checking auth gate on /dashboard"
status="$(curl -s -o /dev/null -w '%{http_code}' "${BASE_URL}/dashboard" "${AUTH_HEADER[@]}")"
if [[ -n "${TOKEN}" ]]; then
  [[ "${status}" == "200" ]] || { echo "Expected 200 with token, got ${status}" >&2; exit 1; }
else
  [[ "${status}" == "303" || "${status}" == "401" ]] || {
    echo "Expected redirect or 401 without token, got ${status}" >&2
    exit 1;
  }
fi

if [[ -n "${TOKEN}" ]]; then
  echo "Checking /api/cloud/readiness"
  curl -fsS "${BASE_URL}/api/cloud/readiness" "${AUTH_HEADER[@]}" >/dev/null
fi

echo "Hosted smoke checks passed for ${BASE_URL}"