#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "Usage: $(basename "$0") <tag> <asset-path> [release-title]" >&2
  exit 1
fi

TAG="$1"
ASSET="$2"
TITLE="${3:-ML Job Swarm ${TAG}}"

if [[ ! -f "${ASSET}" ]]; then
  echo "Release asset not found: ${ASSET}" >&2
  exit 1
fi

if gh release view "${TAG}" >/dev/null 2>&1; then
  echo "Release ${TAG} already exists; uploading asset…"
  gh release upload "${TAG}" "${ASSET}" --clobber
else
  echo "Creating release ${TAG}…"
  gh release create "${TAG}" "${ASSET}" --title "${TITLE}" --generate-notes
fi

echo "Published: ${TAG} -> ${ASSET}"