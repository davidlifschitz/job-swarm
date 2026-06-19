#!/usr/bin/env bash
set -euo pipefail

# Installs ML Job Swarm from a GitHub-downloaded .tar.gz without using
# Finder double-click (which Gatekeeper blocks for unsigned releases).

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="${ML_JOB_SWARM_VERSION:-0.2.0}"
DOWNLOADS="${HOME}/Downloads"
APP_DEST="${HOME}/Applications/MLJobSwarm.app"
TAR_CANDIDATE="${1:-${DOWNLOADS}/MLJobSwarm-${VERSION}-macos-arm64.tar.gz}"
STAGING="$(mktemp -d)"
SIGN_SCRIPT="${ROOT_DIR}/scripts/sign-macos-app.sh"

cleanup() {
  rm -rf "${STAGING}"
}
trap cleanup EXIT

sign_app() {
  local app="$1"
  if [[ -x "${SIGN_SCRIPT}" ]]; then
    "${SIGN_SCRIPT}" "${app}"
    return
  fi
  xattr -cr "${app}" 2>/dev/null || true
  codesign --force --deep --sign - "${app}"
}

install_app_from_source() {
  local app_src="$1"
  if [[ ! -d "${app_src}/Contents/MacOS" ]]; then
    echo "Expected app bundle at ${app_src}" >&2
    exit 1
  fi
  mkdir -p "${HOME}/Applications"
  echo "Installing to ${APP_DEST}…"
  rm -rf "${APP_DEST}"
  ditto "${app_src}" "${APP_DEST}"
  sign_app "${APP_DEST}"
}

if [[ $# -ge 1 && -d "$1" && -d "$1/Contents/MacOS" ]]; then
  install_app_from_source "$1"
elif [[ -f "${TAR_CANDIDATE}" ]]; then
  echo "Using archive: ${TAR_CANDIDATE}"
  xattr -cr "${TAR_CANDIDATE}" 2>/dev/null || true
  tar -xzf "${TAR_CANDIDATE}" -C "${STAGING}"
  install_app_from_source "${STAGING}/MLJobSwarm.app"
else
  cat >&2 <<EOF
Could not find a release artifact to install.

Download this to ${DOWNLOADS}:
  MLJobSwarm-${VERSION}-macos-arm64.tar.gz

Then run:
  ./scripts/install-macos-release.sh

Or pass a path:
  ./scripts/install-macos-release.sh ~/Downloads/MLJobSwarm-${VERSION}-macos-arm64.tar.gz

Prefer Homebrew:
  brew tap davidlifschitz/job-swarm https://github.com/davidlifschitz/job-swarm
  brew install --cask ml-job-swarm
EOF
  exit 1
fi

echo "Launching ML Job Swarm…"
open "${APP_DEST}"
echo "Done."