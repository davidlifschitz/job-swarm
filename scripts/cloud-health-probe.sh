#!/usr/bin/env bash
# Measure /healthz latency p95 and compare against SLO_TARGETS.health_p95_ms.
set -euo pipefail

BASE_URL="${BASE_URL:-}"
PROBE_COUNT="${PROBE_COUNT:-20}"
FALLBACK_HEALTH_P95_MS=200

if [[ -z "${BASE_URL}" ]]; then
  echo "BASE_URL environment variable is required" >&2
  exit 1
fi

BASE_URL="${BASE_URL%/}"
HEALTH_URL="${BASE_URL}/healthz"

body_file="$(mktemp)"
latencies_file="$(mktemp)"
cleanup() {
  rm -f "${body_file}" "${latencies_file}"
}
trap cleanup EXIT

threshold="${FALLBACK_HEALTH_P95_MS}"
for ((probe = 1; probe <= PROBE_COUNT; probe++)); do
  time_total="$(
    curl -fsS -o "${body_file}" -w '%{time_total}' "${HEALTH_URL}"
  )"
  latency_ms="$(
    python3 -c "import sys; print(int(float(sys.argv[1]) * 1000))" "${time_total}"
  )"
  echo "${latency_ms}" >>"${latencies_file}"

  if [[ "${probe}" -eq 1 ]]; then
    threshold="$(
      python3 -c "
import json
import sys

fallback = int(sys.argv[1])
with open(sys.argv[2], encoding='utf-8') as handle:
    payload = json.load(handle)
print(payload.get('slo_targets', {}).get('health_p95_ms', fallback))
" "${FALLBACK_HEALTH_P95_MS}" "${body_file}"
    )"
  fi
done

p95_ms="$(
  python3 -c "
import math
import sys

values = sorted(int(line.strip()) for line in sys.stdin if line.strip())
if not values:
    raise SystemExit('no latency samples collected')
index = max(0, min(math.ceil(0.95 * len(values)) - 1, len(values) - 1))
print(values[index])
" <"${latencies_file}"
)"

if (( p95_ms <= threshold )); then
  pass=true
  exit_code=0
else
  pass=false
  exit_code=1
fi

echo "health_p95_ms=${p95_ms} threshold=${threshold} probes=${PROBE_COUNT} pass=${pass}"
exit "${exit_code}"
