#!/usr/bin/env bash
# Unified maintainer orchestrator for ml-job-swarm production OPS (OPS-1/2/3).
#
# Recommended order: OPS-2 (Supabase) → OPS-1 (Railway cutover) → OPS-3 (notarization).
#
# Usage:
#   ./scripts/run-production-ops.sh --check-env
#   ./scripts/run-production-ops.sh --dry-run
#   ./scripts/run-production-ops.sh --ops-2
#   ./scripts/run-production-ops.sh --ops-1 --dry-run
#   ./scripts/run-production-ops.sh --ops-1
#   ./scripts/run-production-ops.sh --ops-3
#   ./scripts/run-production-ops.sh --all
#   ./scripts/run-production-ops.sh --execute-all
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

# shellcheck source=scripts/lib/ops-env-check.sh
source "${ROOT_DIR}/scripts/lib/ops-env-check.sh"

DO_CHECK_ENV=0
DO_DRY_RUN=0
DO_OPS1=0
DO_OPS2=0
DO_OPS3=0
DO_ALL=0
DO_EXECUTE_ALL=0
OPS1_ARGS=()

usage() {
  cat <<'EOF'
Usage: ./scripts/run-production-ops.sh [OPTIONS]

Unified maintainer orchestrator for production OPS. Recommended order:
  OPS-2 (Supabase bootstrap + secrets) → OPS-1 (Railway cutover) → OPS-3 (macOS notarization)

Options:
  --check-env     Preflight all OPS (1, 2, 3); exit 1 if any are blocked
  --dry-run       Run local ops-readiness checks (verify-ops-readiness.sh)
  --ops-1 [ARGS]  OPS-1: Railway Phase B cutover (delegates to railway-cutover.sh)
  --ops-2         OPS-2: Supabase bootstrap + sync secrets to Railway
  --ops-3         OPS-3: macOS app notarization (--require)
  --all           Run --check-env, then print recommended next commands (does not run live OPS)
  --execute-all   Run --check-env; if complete, execute OPS-2 → OPS-1 → OPS-3 in sequence
  -h, --help      Show this help

Examples:
  ./scripts/run-production-ops.sh --check-env
  ./scripts/run-production-ops.sh --dry-run
  ./scripts/run-production-ops.sh --ops-1 --dry-run
  ./scripts/run-production-ops.sh --ops-2
  ./scripts/run-production-ops.sh --all
  ./scripts/run-production-ops.sh --execute-all
EOF
}

run_check_env() {
  local failed=0

  echo "==> Production OPS environment preflight (OPS-1, OPS-2, OPS-3)"
  echo

  if ! ops_report_missing 1; then
    failed=1
  fi
  echo

  if ! ops_report_missing 2; then
    failed=1
  fi
  echo

  if ! ops_report_missing 3; then
    failed=1
  fi
  echo

  if (( failed )); then
    echo "Environment preflight: BLOCKED — fix missing prerequisites above."
    return 1
  fi

  echo "Environment preflight: OK — all OPS prerequisites present."
  return 0
}

run_dry_run() {
  echo "==> Local ops-readiness dry-run"
  ./scripts/verify-ops-readiness.sh
}

run_ops1() {
  echo "==> OPS-1: Railway Phase B cutover"
  ops_check_ops1
  echo
  ./scripts/railway-cutover.sh "${OPS1_ARGS[@]}"
}

run_ops2() {
  echo "==> OPS-2: Supabase bootstrap + Railway secret sync"
  ops_check_ops2
  echo
  ./scripts/bootstrap-supabase.sh
  ./scripts/sync-supabase-secrets.sh --railway
}

run_ops3() {
  echo "==> OPS-3: macOS app notarization"
  ops_check_ops3
  echo
  ./scripts/notarize-macos-app.sh --require
}

print_all_next_steps() {
  cat <<'EOF'

Recommended production OPS order (run explicitly — nothing live runs automatically):

  1. OPS-2 — Supabase bootstrap and Railway secret sync:
       ./scripts/run-production-ops.sh --ops-2

  2. OPS-1 — Railway Phase B cutover (dry-run first):
       ./scripts/run-production-ops.sh --ops-1 --dry-run
       ./scripts/run-production-ops.sh --ops-1

  3. OPS-3 — macOS notarization (macOS + Apple Developer creds):
       ./scripts/run-production-ops.sh --ops-3

Or run the full sequence when env is complete:
       ./scripts/run-production-ops.sh --execute-all
EOF
}

run_all() {
  run_check_env || true
  print_all_next_steps
}

run_execute_all() {
  run_check_env
  echo
  echo "==> Executing OPS-2 → OPS-1 → OPS-3"
  echo
  run_ops2
  echo
  run_ops1
  echo
  run_ops3
  echo
  echo "All production OPS steps completed."
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --check-env)
      DO_CHECK_ENV=1
      shift
      ;;
    --dry-run)
      DO_DRY_RUN=1
      shift
      ;;
    --ops-1)
      DO_OPS1=1
      shift
      OPS1_ARGS=("$@")
      set --
      ;;
    --ops-2)
      DO_OPS2=1
      shift
      ;;
    --ops-3)
      DO_OPS3=1
      shift
      ;;
    --all)
      DO_ALL=1
      shift
      ;;
    --execute-all)
      DO_EXECUTE_ALL=1
      shift
      ;;
    -h | --help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      echo "Run ./scripts/run-production-ops.sh --help for usage." >&2
      exit 1
      ;;
  esac
done

if (( DO_CHECK_ENV + DO_DRY_RUN + DO_OPS1 + DO_OPS2 + DO_OPS3 + DO_ALL + DO_EXECUTE_ALL == 0 )); then
  usage
  exit 1
fi

if (( DO_ALL )); then
  run_all
  exit 0
fi

if (( DO_EXECUTE_ALL )); then
  run_execute_all
  exit 0
fi

exit_code=0

if (( DO_CHECK_ENV )); then
  run_check_env || exit_code=1
fi

if (( DO_DRY_RUN )); then
  run_dry_run || exit_code=1
fi

if (( DO_OPS2 )); then
  run_ops2 || exit_code=1
fi

if (( DO_OPS1 )); then
  run_ops1 || exit_code=1
fi

if (( DO_OPS3 )); then
  run_ops3 || exit_code=1
fi

exit "${exit_code}"
