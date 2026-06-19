#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $(basename "$0") /path/to/MLJobSwarm.app" >&2
  exit 1
fi

APP="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
if [[ ! -d "${APP}/Contents/MacOS" ]]; then
  echo "Not a macOS app bundle: ${APP}" >&2
  exit 1
fi

if ! command -v codesign >/dev/null 2>&1; then
  echo "codesign is required (Xcode command line tools)." >&2
  exit 1
fi

echo "Clearing download quarantine attributes…"
xattr -cr "${APP}" 2>/dev/null || true

echo "Ad-hoc signing Mach-O binaries in bundle…"
while IFS= read -r -d '' binary; do
  codesign --force --sign - "${binary}" >/dev/null 2>&1 || true
done < <(
  find "${APP}" -type f -print0 | while IFS= read -r -d '' file; do
    if file -b "${file}" 2>/dev/null | grep -q 'Mach-O'; then
      printf '%s\0' "${file}"
    fi
  done
)

IDENTITY="${CODESIGN_IDENTITY:--}"

echo "Sealing app bundle signature (${IDENTITY})…"
if [[ "${IDENTITY}" == "-" ]]; then
  codesign --force --deep --sign - "${APP}"
else
  codesign --force --deep --sign "${IDENTITY}" --options runtime --timestamp "${APP}"
fi

echo "Signed: ${APP}"