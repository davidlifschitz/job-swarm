#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="${1:-0.2.1}"
DIST_DIR="${ROOT_DIR}/macos/dist"
APP_BUNDLE="${DIST_DIR}/MLJobSwarm.app"
ARCHIVE_NAME="MLJobSwarm-${VERSION}-macos-arm64.tar.gz"
ARCHIVE_PATH="${DIST_DIR}/${ARCHIVE_NAME}"

echo "Building signed macOS app (v${VERSION})…"
APP_VERSION="${VERSION}" INSTALL_DIR="${DIST_DIR}" "${ROOT_DIR}/scripts/build-macos-app.sh"

if [[ ! -d "${APP_BUNDLE}" ]]; then
  echo "Expected app bundle missing: ${APP_BUNDLE}" >&2
  exit 1
fi

echo "Running release smoke test…"
"${ROOT_DIR}/scripts/smoke-macos-release.sh" "${APP_BUNDLE}"

echo "Creating release archive ${ARCHIVE_NAME}…"
rm -f "${ARCHIVE_PATH}"
(
  cd "${DIST_DIR}"
  COPYFILE_DISABLE=1 tar -czf "${ARCHIVE_NAME}" MLJobSwarm.app
)

echo ""
echo "Release artifact:"
echo "  tar.gz: ${ARCHIVE_PATH}"
echo ""
echo "After uploading the release, bump the Homebrew cask:"
echo "  ./scripts/bump-homebrew-cask.sh ${VERSION} ${ARCHIVE_PATH}"