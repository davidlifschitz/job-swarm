# Tier 1 — macOS GitHub release

## Ship checklist

1. `uv run pytest -q` passes
2. `./scripts/package-macos-release.sh <version>` produces tar.gz
3. `./scripts/smoke-macos-release.sh macos/dist/MLJobSwarm.app` passes
4. Tag `v<version>` → GitHub Actions uploads the archive and bumps the Homebrew cask on `main`

## Distribution

| Channel | Command |
|---------|---------|
| Homebrew cask | `brew tap davidlifschitz/job-swarm https://github.com/davidlifschitz/job-swarm && brew trust davidlifschitz/job-swarm && brew install --cask ml-job-swarm` |
| Terminal installer | `./scripts/install-macos-release.sh ~/Downloads/MLJobSwarm-<version>-macos-arm64.tar.gz` |
| Build from source | `./scripts/build-macos-app.sh` |

Release artifacts are **tar.gz only** (no DMG). The cask downloads the public GitHub release URL.

Homebrew install prerequisites:

- `brew tap davidlifschitz/job-swarm https://github.com/davidlifschitz/job-swarm`
- `brew trust davidlifschitz/job-swarm` (Homebrew 6 third-party tap policy)

## CI

- `.github/workflows/ci.yml` — pytest on Ubuntu, build + smoke on `macos-14`
- `.github/workflows/release-macos.yml` — tag `v*.*.*` builds, uploads tar.gz, commits cask bump to `main`