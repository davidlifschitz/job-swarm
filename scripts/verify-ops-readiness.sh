#!/usr/bin/env bash
# Run local Tier 2 pre-cutover checks (no production secrets).
#
# Covers docs/tier2-hosted-web.md dry-run steps 5–7 and 9. Skips Docker
# preflight (steps 2–3) and live health probe (step 8) unless BASE_URL is set.
#
# Usage:
#   ./scripts/verify-ops-readiness.sh
#   BASE_URL=http://127.0.0.1:8765 ./scripts/verify-ops-readiness.sh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

PRODUCT_GATE_TESTS=(
  tests/test_product_goals.py
  tests/test_seed_policy_gate.py
  tests/test_seed_refresh_audit.py
  tests/test_golden_profile_matching.py
  tests/test_catalog_quality_gate.py
  tests/test_error_handling_gates.py
  tests/test_operator_observability_gate.py
)

echo "==> Product gate tests"
uv run pytest -q "${PRODUCT_GATE_TESTS[@]}"

echo "==> Hosted env template gate"
uv run pytest -q tests/test_hosted_env_template.py

echo "==> Cloud parity fixtures"
chmod +x scripts/run-cloud-parity-check.sh
./scripts/run-cloud-parity-check.sh

echo "==> Cloud load capacity fixture"
uv run python scripts/run-cloud-load-test.py

echo "==> Offline seed refresh audit"
AUDIT_DB="$(mktemp /tmp/seed-audit-XXXXXX.db)"
SUBSET_SEED="$(mktemp /tmp/seed-audit-subset-XXXXXX.json)"
trap 'rm -f "${AUDIT_DB}" "${SUBSET_SEED}"' EXIT
uv run python - <<PY
from pathlib import Path
import importlib.util

spec = importlib.util.spec_from_file_location(
    "seed_refresh_audit",
    "${ROOT_DIR}/scripts/seed_refresh_audit.py",
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.write_fixture_seed_subset(Path("${SUBSET_SEED}"))
PY
uv run python scripts/seed_refresh_audit.py --db "${AUDIT_DB}" --seed "${SUBSET_SEED}"

echo "==> Railway cutover dry-run (temp SQLite export)"
CUTover_DB="$(mktemp /tmp/cutover-dry-run-XXXXXX.db)"
CUTover_RESUME="$(mktemp -d /tmp/cutover-resume-XXXXXX)"
trap 'rm -f "${AUDIT_DB}" "${SUBSET_SEED}"; rm -f "${CUTover_DB}"; rm -rf "${CUTover_RESUME}"' EXIT
uv run python - <<PY
from pathlib import Path
from tests.test_hosted_migration import _seed_sqlite

_seed_sqlite(Path("${CUTover_DB}"), resume_dir=Path("${CUTover_RESUME}"))
PY
ML_JOB_SWARM_SOURCE_DB="${CUTover_DB}" \
  ML_JOB_SWARM_RESUME_ASSET_DIR="${CUTover_RESUME}" \
  ./scripts/railway-cutover.sh --dry-run

if [[ -n "${BASE_URL:-}" ]]; then
  echo "==> Cloud health probe (${BASE_URL})"
  chmod +x scripts/cloud-health-probe.sh
  BASE_URL="${BASE_URL}" ./scripts/cloud-health-probe.sh
else
  echo "==> Cloud health probe skipped (set BASE_URL to run step 8)"
fi

echo "All local ops-readiness checks passed."
