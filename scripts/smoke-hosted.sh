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

echo "Checking ${BASE_URL}/healthz"
health="$(curl -fsS "${BASE_URL}/healthz")"
echo "${health}" | python3 -c "import json,sys; d=json.load(sys.stdin); assert d['status']=='ok', d"

echo "Checking auth gate on /dashboard"
if [[ -n "${TOKEN}" ]]; then
  status="$(curl -s -o /dev/null -w '%{http_code}' "${BASE_URL}/dashboard" -H "Authorization: Bearer ${TOKEN}")"
else
  status="$(curl -s -o /dev/null -w '%{http_code}' "${BASE_URL}/dashboard")"
fi
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
  curl -fsS "${BASE_URL}/api/cloud/readiness" -H "Authorization: Bearer ${TOKEN}" >/dev/null
fi

echo "Hosted smoke checks passed for ${BASE_URL}"