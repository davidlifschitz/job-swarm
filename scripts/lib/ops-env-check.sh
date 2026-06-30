#!/usr/bin/env bash
# Maintainer environment preflight for ml-job-swarm production OPS (OPS-1/2/3).
#
# Source from bash scripts:
#   source "$(dirname "${BASH_SOURCE[0]}")/lib/ops-env-check.sh"
#
# Exports:
#   ops_require_var          — fail fast when a required var is unset/empty
#   ops_check_ops1           — Railway Phase B live cutover env (OPS-1)
#   ops_check_ops2           — Supabase CLI login and project ref (OPS-2)
#   ops_check_ops3           — Apple notarization credentials and xcrun (OPS-3)
#   ops_report_missing       — human-readable report for a given OPS number

[[ -n "${OPS_ENV_CHECK_LOADED:-}" ]] && return 0
OPS_ENV_CHECK_LOADED=1

set -euo pipefail

OPS_MISSING=()

ops_require_var() {
  local name="$1"
  if [[ -z "${!name:-}" ]]; then
    echo "Required environment variable is unset or empty: ${name}" >&2
    exit 1
  fi
}

_ops_reset_missing() {
  OPS_MISSING=()
}

_ops_add_missing() {
  OPS_MISSING+=("$1")
}

_ops_var_present() {
  local name="$1"
  [[ -n "${!name:-}" ]]
}

ops_check_ops1() {
  _ops_reset_missing

  if ! _ops_var_present DATABASE_URL; then
    _ops_add_missing "DATABASE_URL"
  fi
  if ! _ops_var_present ML_JOB_SWARM_SOURCE_DB; then
    _ops_add_missing "ML_JOB_SWARM_SOURCE_DB"
  fi

  if ((${#OPS_MISSING[@]} > 0)); then
    echo "OPS-1 (Railway Phase B cutover) — missing required variables:"
    for item in "${OPS_MISSING[@]}"; do
      echo "  - ${item}"
    done
    return 1
  fi

  echo "OPS-1 (Railway Phase B cutover) — required variables present:"
  echo "  - DATABASE_URL"
  echo "  - ML_JOB_SWARM_SOURCE_DB"
  if _ops_var_present ML_JOB_SWARM_RESUME_ASSET_DIR; then
    echo "  - ML_JOB_SWARM_RESUME_ASSET_DIR (optional, set)"
  else
    echo "  - ML_JOB_SWARM_RESUME_ASSET_DIR (optional, not set)"
  fi
  return 0
}

ops_check_ops2() {
  _ops_reset_missing
  local cli_ok=0 login_ok=0

  if command -v supabase >/dev/null 2>&1; then
    cli_ok=1
    echo "OPS-2 (Supabase hygiene) — Supabase CLI: installed"
  else
    _ops_add_missing "supabase CLI (install: brew install supabase/tap/supabase)"
    echo "OPS-2 (Supabase hygiene) — Supabase CLI: not found"
  fi

  if (( cli_ok )); then
    if supabase projects list >/dev/null 2>&1; then
      login_ok=1
      echo "OPS-2 (Supabase hygiene) — Supabase login: active"
    else
      _ops_add_missing "supabase login (run: supabase login or supabase login --token \"\$SUPABASE_ACCESS_TOKEN\")"
      echo "OPS-2 (Supabase hygiene) — Supabase login: not logged in"
    fi
  fi

  if _ops_var_present SUPABASE_PROJECT_REF; then
    echo "OPS-2 (Supabase hygiene) — SUPABASE_PROJECT_REF: ${SUPABASE_PROJECT_REF}"
  else
    echo "OPS-2 (Supabase hygiene) — SUPABASE_PROJECT_REF: not set (optional; sync script uses default project ref)"
  fi

  if ((${#OPS_MISSING[@]} > 0)); then
    echo "OPS-2 (Supabase hygiene) — missing prerequisites:"
    for item in "${OPS_MISSING[@]}"; do
      echo "  - ${item}"
    done
    return 1
  fi

  return 0
}

ops_check_ops3() {
  _ops_reset_missing
  local cred_mode=""

  if _ops_var_present NOTARYTOOL_PROFILE; then
    cred_mode="NOTARYTOOL_PROFILE"
    echo "OPS-3 (Apple notarization) — credentials: NOTARYTOOL_PROFILE set"
  elif _ops_var_present APPLE_ID && _ops_var_present APPLE_APP_SPECIFIC_PASSWORD && _ops_var_present APPLE_TEAM_ID; then
    cred_mode="APPLE_ID bundle"
    echo "OPS-3 (Apple notarization) — credentials: APPLE_ID + APPLE_APP_SPECIFIC_PASSWORD + APPLE_TEAM_ID"
  else
    _ops_add_missing "NOTARYTOOL_PROFILE or (APPLE_ID + APPLE_APP_SPECIFIC_PASSWORD + APPLE_TEAM_ID)"
    echo "OPS-3 (Apple notarization) — credentials: incomplete"
  fi

  case "$(uname -s)" in
    Darwin)
      if command -v xcrun >/dev/null 2>&1; then
        echo "OPS-3 (Apple notarization) — xcrun: available"
      else
        _ops_add_missing "xcrun (install Xcode Command Line Tools)"
        echo "OPS-3 (Apple notarization) — xcrun: not found"
      fi
      ;;
    *)
      echo "OPS-3 (Apple notarization) — xcrun: skipped (not macOS; notarization runs on macOS only)"
      ;;
  esac

  if [[ -z "${cred_mode}" ]] || ((${#OPS_MISSING[@]} > 0)); then
    if ((${#OPS_MISSING[@]} > 0)); then
      echo "OPS-3 (Apple notarization) — missing prerequisites:"
      for item in "${OPS_MISSING[@]}"; do
        echo "  - ${item}"
      done
    fi
    return 1
  fi

  return 0
}

ops_report_missing() {
  local ops_num="${1:-}"
  case "${ops_num}" in
    1 | ops-1 | OPS-1)
      echo "==> Maintainer env preflight: OPS-1 (Railway Phase B cutover)"
      ops_check_ops1
      ;;
    2 | ops-2 | OPS-2)
      echo "==> Maintainer env preflight: OPS-2 (Supabase hygiene)"
      ops_check_ops2
      ;;
    3 | ops-3 | OPS-3)
      echo "==> Maintainer env preflight: OPS-3 (Apple notarization)"
      ops_check_ops3
      ;;
    *)
      echo "Unknown OPS number: ${ops_num} (expected 1, 2, or 3)" >&2
      return 1
      ;;
  esac
}

export -f ops_require_var ops_check_ops1 ops_check_ops2 ops_check_ops3 ops_report_missing
