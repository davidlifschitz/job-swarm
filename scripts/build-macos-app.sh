#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MACOS_DIR="${ROOT_DIR}/macos/MLJobSwarm"
APP_NAME="ML Job Swarm"
APP_VERSION="${APP_VERSION:-0.2.1}"
BUNDLE_ID="com.davidlifschitz.ml-job-swarm"
INSTALL_DIR="${INSTALL_DIR:-${HOME}/Applications}"
DIST_DIR="${ROOT_DIR}/macos/dist"
APP_BUNDLE="${DIST_DIR}/MLJobSwarm.app"
BACKEND_DIR="${APP_BUNDLE}/Contents/Resources/backend"

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required to bundle the Python backend. Install from https://docs.astral.sh/uv/" >&2
  exit 1
fi

echo "Building release binary…"
cd "${MACOS_DIR}"
swift build -c release

BINARY="${MACOS_DIR}/.build/arm64-apple-macosx/release/MLJobSwarm"
if [[ ! -f "${BINARY}" ]]; then
  echo "Expected binary not found: ${BINARY}" >&2
  exit 1
fi

echo "Packaging ${APP_BUNDLE}…"
rm -rf "${APP_BUNDLE}"
mkdir -p "${APP_BUNDLE}/Contents/MacOS"
mkdir -p "${APP_BUNDLE}/Contents/Resources"
ICON_SOURCE="${MACOS_DIR}/AppIcon.icns"
if [[ -f "${ICON_SOURCE}" ]]; then
  cp "${ICON_SOURCE}" "${APP_BUNDLE}/Contents/Resources/AppIcon.icns"
fi

cat > "${APP_BUNDLE}/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleDevelopmentRegion</key>
  <string>en</string>
  <key>CFBundleExecutable</key>
  <string>MLJobSwarm</string>
  <key>CFBundleIdentifier</key>
  <string>${BUNDLE_ID}</string>
  <key>CFBundleInfoDictionaryVersion</key>
  <string>6.0</string>
  <key>CFBundleName</key>
  <string>${APP_NAME}</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>CFBundleShortVersionString</key>
  <string>${APP_VERSION}</string>
  <key>CFBundleVersion</key>
  <string>${APP_VERSION}</string>
  <key>LSMinimumSystemVersion</key>
  <string>14.0</string>
  <key>NSHighResolutionCapable</key>
  <true/>
  <key>CFBundleIconFile</key>
  <string>AppIcon</string>
</dict>
</plist>
PLIST

cp "${BINARY}" "${APP_BUNDLE}/Contents/MacOS/MLJobSwarm"
chmod +x "${APP_BUNDLE}/Contents/MacOS/MLJobSwarm"

echo "Bundling Python backend into app resources…"
mkdir -p "${BACKEND_DIR}/data"
cp "${ROOT_DIR}/pyproject.toml" "${BACKEND_DIR}/"
if [[ -f "${ROOT_DIR}/README.md" ]]; then
  cp "${ROOT_DIR}/README.md" "${BACKEND_DIR}/"
fi
if [[ -f "${ROOT_DIR}/uv.lock" ]]; then
  cp "${ROOT_DIR}/uv.lock" "${BACKEND_DIR}/"
fi
cp -R "${ROOT_DIR}/ml_job_swarm" "${BACKEND_DIR}/"
if [[ -f "${ROOT_DIR}/data/seed_companies.json" ]]; then
  cp "${ROOT_DIR}/data/seed_companies.json" "${BACKEND_DIR}/data/"
fi

echo "Creating bundled virtualenv (this may take a minute)…"
(
  cd "${BACKEND_DIR}"
  if [[ -f uv.lock ]]; then
    uv sync --frozen --no-dev
  else
    uv sync --no-dev
  fi
)

if [[ ! -x "${BACKEND_DIR}/.venv/bin/python3" ]]; then
  echo "Bundled backend venv was not created: ${BACKEND_DIR}/.venv/bin/python3" >&2
  exit 1
fi

echo "Signing app bundle for Gatekeeper…"
"${ROOT_DIR}/scripts/sign-macos-app.sh" "${APP_BUNDLE}"

TARGET_APP="${INSTALL_DIR}/MLJobSwarm.app"
if [[ "$(cd "$(dirname "${APP_BUNDLE}")" && pwd -P)/$(basename "${APP_BUNDLE}")" == "$(cd "$(dirname "${TARGET_APP}")" 2>/dev/null && pwd -P)/$(basename "${TARGET_APP}")" ]]; then
  echo ""
  echo "Built: ${APP_BUNDLE}"
else
  mkdir -p "${INSTALL_DIR}"
  rm -rf "${TARGET_APP}"
  ditto "${APP_BUNDLE}" "${TARGET_APP}"
  echo ""
  echo "Installed: ${TARGET_APP}"
fi
echo "Launch from Finder → Applications, Spotlight (Cmd+Space → ML Job Swarm), or:"
echo "  open \"${TARGET_APP}\""