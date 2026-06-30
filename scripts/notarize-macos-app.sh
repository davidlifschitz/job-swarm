#!/usr/bin/env bash
# Submit a packaged macOS app for Apple notarization (Tier 3).
#
# Requires Apple Developer credentials. Skips gracefully when secrets are unset,
# unless --require is passed (then missing creds exit 1).
#
# Usage:
#   APP=macos/dist/MLJobSwarm.app ./scripts/notarize-macos-app.sh
#   APP=macos/dist/MLJobSwarm.app ZIP=out.zip ./scripts/notarize-macos-app.sh
#   ./scripts/notarize-macos-app.sh --require
set -euo pipefail

REQUIRE_NOTARIZATION=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --require)
      REQUIRE_NOTARIZATION=1
      shift
      ;;
    *)
      echo "Unknown argument: $1" >&2
      echo "Usage: $0 [--require]" >&2
      exit 1
      ;;
  esac
done

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

APP="${APP:-macos/dist/MLJobSwarm.app}"
ZIP="${ZIP:-${APP%.app}-notarize.zip}"

if [[ ! -d "${APP}" ]]; then
  echo "App bundle not found: ${APP}" >&2
  exit 1
fi

if [[ -z "${NOTARYTOOL_PROFILE:-}" && -z "${APPLE_ID:-}" ]]; then
  echo "Notarization skipped: set NOTARYTOOL_PROFILE or APPLE_ID + APPLE_APP_SPECIFIC_PASSWORD." >&2
  echo "See docs/tier3-app-stores.md for Tier 3 setup." >&2
  if [[ "${REQUIRE_NOTARIZATION}" -eq 1 ]]; then
    exit 1
  fi
  exit 0
fi

if ! command -v xcrun >/dev/null 2>&1; then
  echo "xcrun is required (Xcode command line tools)." >&2
  exit 1
fi

echo "==> Codesigning ${APP}"
export CODESIGN_IDENTITY="${CODESIGN_IDENTITY:--}"
./scripts/sign-macos-app.sh "${APP}"

echo "==> Creating zip for notary submission"
ditto -c -k --keepParent "${APP}" "${ZIP}"

echo "==> Submitting to Apple notary service"
if [[ -n "${NOTARYTOOL_PROFILE:-}" ]]; then
  xcrun notarytool submit "${ZIP}" --keychain-profile "${NOTARYTOOL_PROFILE}" --wait
else
  xcrun notarytool submit "${ZIP}" \
    --apple-id "${APPLE_ID}" \
    --password "${APPLE_APP_SPECIFIC_PASSWORD}" \
    --team-id "${APPLE_TEAM_ID}" \
    --wait
fi

echo "==> Stapling ticket"
xcrun stapler staple "${APP}"
echo "Notarization complete: ${APP}"