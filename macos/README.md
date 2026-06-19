# ml-job-swarm macOS app

Native SwiftUI shell for the existing local-first Python engine.

## Architecture

- **SwiftUI app** (`macos/MLJobSwarm`) is the desktop UI.
- **Python backend** (`ml_job_swarm`) still owns SQLite, job matching, LinkedIn import, and source refresh.
- The app launches a bundled `uvicorn` process on startup and talks to `/api/v1/*` on a dynamic localhost port.
- App data lives in `~/Library/Application Support/MLJobSwarm/jobs.db`.
- OpenRouter keys are stored in macOS Keychain (`LLMSettingsStore`); never written to the repo.

## Install

Download and install instructions are in the [root README](../README.md#install-ml-job-swarm-macos).

Build from source:

```bash
uv sync
chmod +x scripts/build-macos-app.sh scripts/sign-macos-app.sh
./scripts/build-macos-app.sh
open ~/Applications/MLJobSwarm.app
```

The installer writes to `~/Applications/MLJobSwarm.app`. Build artifacts under `macos/dist/` are gitignored.

## Run from terminal (dev)

```bash
./scripts/run-macos-app.sh
```

Or open `macos/MLJobSwarm` in Xcode and run the `MLJobSwarm` scheme.

## App icon

`macos/MLJobSwarm/AppIcon.icns` is bundled by `scripts/build-macos-app.sh`. Source artwork is in `design-specs/`.

## SnapshotPreviews

This app uses [getsentry/SnapshotPreviews](https://github.com/getsentry/SnapshotPreviews) for preview-driven snapshot tests.

```bash
cd macos/MLJobSwarm
TEST_RUNNER_SNAPSHOTS_EXPORT_DIR="$PWD/snapshot-images" \
xcodebuild test \
  -scheme MLJobSwarm \
  -destination 'platform=macOS'
```

Preview fixtures use fictional names only (`PreviewFixtures.swift`).

## Native coverage (v0.2.0)

- Dashboard with referral network, filter chips, careers refresh, and fit review
- LinkedIn connections import and catalog matching
- LLM settings with Keychain storage, live usage dashboard, legacy `.env` one-time import (local machine only)
- Source health with refresh-all and per-source refresh
- Saved jobs, job detail, onboarding, and admin source health