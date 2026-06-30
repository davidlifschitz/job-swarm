#!/usr/bin/env bash
# OPS-2 Supabase bootstrap: link project, apply migrations, Storage guidance.
#
# Prerequisites:
#   brew install supabase/tap/supabase
#   supabase login   # or: supabase login --token "$SUPABASE_ACCESS_TOKEN"
#
# Usage:
#   ./scripts/bootstrap-supabase.sh --check-env
#   ./scripts/bootstrap-supabase.sh --dry-run
#   ./scripts/bootstrap-supabase.sh
#
# After bootstrap, sync secrets locally / to Railway:
#   ./scripts/sync-supabase-secrets.sh
#   ./scripts/sync-supabase-secrets.sh --railway
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

POLICIES_SQL="${ROOT_DIR}/supabase/storage/resume-assets-policies.sql"
BUCKET_NAME="${ML_JOB_SWARM_RESUME_STORAGE_BUCKET:-resume-assets}"

CHECK_ENV=0
DRY_RUN=0

for arg in "$@"; do
  case "${arg}" in
    --check-env) CHECK_ENV=1 ;;
    --dry-run) DRY_RUN=1 ;;
    -h|--help)
      sed -n '2,16p' "$0"
      exit 0
      ;;
    *)
      echo "Unknown argument: ${arg}" >&2
      exit 1
      ;;
  esac
done

resolve_project_ref() {
  if [[ -n "${SUPABASE_PROJECT_REF:-}" ]]; then
    echo "${SUPABASE_PROJECT_REF}"
    return 0
  fi
  local config="${ROOT_DIR}/supabase/config.toml"
  if [[ -f "${config}" ]]; then
    local ref
    ref="$(grep -E '^project_id[[:space:]]*=' "${config}" | head -1 \
      | sed -E 's/^project_id[[:space:]]*=[[:space:]]*"([^"]+)".*/\1/')"
    if [[ -n "${ref}" ]]; then
      echo "${ref}"
      return 0
    fi
  fi
  echo "qyxrbcbmatbaywyjrtug"
}

PROJECT_REF="$(resolve_project_ref)"

check_supabase_cli() {
  command -v supabase >/dev/null 2>&1
}

check_supabase_login() {
  supabase projects list >/dev/null 2>&1
}

collect_env_missing() {
  local missing=()
  if ! check_supabase_cli; then
    missing+=("Supabase CLI — install: brew install supabase/tap/supabase")
  elif ! check_supabase_login; then
    missing+=("Supabase CLI login — run: supabase login")
    missing+=("Or: supabase login --token \"\$SUPABASE_ACCESS_TOKEN\"")
    missing+=("Token: https://supabase.com/dashboard/account/tokens")
  fi
  if [[ ${#missing[@]} -gt 0 ]]; then
    printf '%s\n' "${missing[@]}"
  fi
}

run_check_env() {
  local missing
  missing="$(collect_env_missing || true)"
  if [[ -n "${missing}" ]]; then
    echo "OPS-2 Supabase bootstrap — missing prerequisites:"
    while IFS= read -r line; do
      [[ -n "${line}" ]] && echo "  - ${line}"
    done <<< "${missing}"
    return 1
  fi
  echo "OPS-2 Supabase bootstrap — environment OK"
  echo "  Supabase CLI: installed ($(command -v supabase))"
  echo "  Supabase login: active"
  echo "  Project ref: ${PROJECT_REF} (override with SUPABASE_PROJECT_REF)"
  return 0
}

print_storage_instructions() {
  cat <<EOF

==> Storage bucket (dashboard — CLI cannot create private buckets reliably)
  1. Supabase Dashboard → Storage → New bucket
     Name: ${BUCKET_NAME}
     Public: off (private)
  2. SQL Editor → run policies from:
     ${POLICIES_SQL}

==> Auth (dashboard)
  Enable Email provider: Authentication → Providers → Email

==> Secrets (after link + db push)
  ./scripts/sync-supabase-secrets.sh          # writes .env.supabase.local
  ./scripts/sync-supabase-secrets.sh --railway # pushes publishable key to Railway

  Copy from Project Settings → API Keys:
    SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY
  Copy session pooler URI → DATABASE_URL (Settings → Database)
EOF
}

run_dry_run() {
  echo "OPS-2 Supabase bootstrap — dry run (no changes applied)"
  echo
  echo "Would run from ${ROOT_DIR}:"
  echo "  supabase link --project-ref ${PROJECT_REF}"
  echo "  supabase db push --linked"
  print_storage_instructions
}

run_bootstrap() {
  echo "==> Linking Supabase project ${PROJECT_REF}"
  supabase link --project-ref "${PROJECT_REF}"

  echo "==> Applying migrations (supabase db push --linked)"
  supabase db push --linked

  echo
  echo "Bootstrap complete: project linked and migrations applied."
  print_storage_instructions
}

if [[ "${CHECK_ENV}" -eq 1 ]]; then
  run_check_env
  exit $?
fi

if [[ "${DRY_RUN}" -eq 1 ]]; then
  run_dry_run
  exit 0
fi

if ! run_check_env; then
  exit 1
fi

run_bootstrap
