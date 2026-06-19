# Tier 1 — macOS GitHub release

**Status: complete** — public installs via Homebrew or GitHub Releases on [job-swarm](https://github.com/davidlifschitz/job-swarm).

## Ship checklist

1. `uv run pytest -q` passes
2. `./scripts/package-macos-release.sh <version>` produces tar.gz
3. `./scripts/smoke-macos-release.sh macos/dist/MLJobSwarm.app` passes
4. Tag `v<version>` on `main` → GitHub Actions publishes the release and bumps the Homebrew cask

## Distribution

| Channel | Command |
|---------|---------|
| Homebrew cask | `brew tap davidlifschitz/job-swarm https://github.com/davidlifschitz/job-swarm && brew trust davidlifschitz/job-swarm && brew install --cask ml-job-swarm` |
| Terminal installer | `./scripts/install-macos-release.sh ~/Downloads/MLJobSwarm-<version>-macos-arm64.tar.gz` |
| Build from source | `./scripts/build-macos-app.sh` |

Release artifacts are **tar.gz only** (no DMG). The cask downloads the public GitHub release URL.

## Release automation

Tag push runs `.github/workflows/release-macos.yml`:

1. pytest on `macos-14`
2. `./scripts/package-macos-release.sh`
3. `./scripts/publish-github-release.sh` (creates release or re-uploads asset with `--clobber`)
4. `./scripts/bump-homebrew-cask.sh`
5. Commits updated cask to `main`

## CI

- `.github/workflows/ci.yml` — pytest on Ubuntu, build + smoke on `macos-14`
- `.github/workflows/release-macos.yml` — tag `v*.*.*`