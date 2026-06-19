#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "Usage: $(basename "$0") <version> <archive-path>" >&2
  exit 1
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="$1"
ARCHIVE_PATH="$2"
CASK_FILE="${ROOT_DIR}/Casks/ml-job-swarm.rb"

if [[ ! -f "${ARCHIVE_PATH}" ]]; then
  echo "Archive not found: ${ARCHIVE_PATH}" >&2
  exit 1
fi

if [[ ! -f "${CASK_FILE}" ]]; then
  echo "Cask file not found: ${CASK_FILE}" >&2
  exit 1
fi

SHA256="$(shasum -a 256 "${ARCHIVE_PATH}" | awk '{print $1}')"

perl -0pi -e "s/version \"[^\"]+\"/version \"${VERSION}\"/; s/sha256 \"[^\"]+\"/sha256 \"${SHA256}\"/" "${CASK_FILE}"

echo "Updated ${CASK_FILE}"
echo "  version: ${VERSION}"
echo "  sha256:  ${SHA256}"