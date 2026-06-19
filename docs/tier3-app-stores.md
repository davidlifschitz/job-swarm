# Tier 3 — App stores

**Status: not started** — Tier 1 (GitHub/Homebrew) and Tier 2 Phase B (hosted Postgres) ship first.

## Goal

Distribute ml-job-swarm through official app stores in addition to GitHub/Homebrew (Tier 1) and the hosted web console (Tier 2).

| Platform | Target | Blocker |
|----------|--------|---------|
| macOS | Mac App Store or notarized direct download | Apple Developer Program + notarized release pipeline |
| Android | Native app or installable PWA | Store strategy TBD |

## macOS — notarized distribution

Today Tier 1 builds are ad-hoc signed (`codesign --sign -`). README notes Gatekeeper warnings on browser download.

### Ship checklist

1. Enroll in [Apple Developer Program](https://developer.apple.com/programs/)
2. Create **Developer ID Application** certificate for distribution outside MAS
3. Store credentials in CI secrets:
   - `APPLE_ID`, `APPLE_APP_SPECIFIC_PASSWORD` or App Store Connect API key
   - `CODESIGN_IDENTITY` (Developer ID)
   - `NOTARYTOOL_PROFILE` or key id / issuer / p8 key for `notarytool`
4. Run `./scripts/notarize-macos-app.sh` after `package-macos-release.sh`
5. Staple ticket: `xcrun stapler staple MLJobSwarm.app`
6. Publish notarized tar.gz; update Homebrew cask to verify stapled bundle
7. (Optional) Mac App Store: sandbox entitlements, MAS provisioning, separate build flavor

### Scripts

| Script | Role |
|--------|------|
| `scripts/sign-macos-app.sh` | Codesign with `CODESIGN_IDENTITY` |
| `scripts/notarize-macos-app.sh` | Submit to Apple notary service (requires secrets) |
| `scripts/package-macos-release.sh` | Produce release tarball |

## Android / PWA

Pick one path before implementation:

- **PWA**: hosted Tier 2 app + Web App Manifest + service worker; installable from Safari/Chrome
- **Native Android**: Tauri/React Native wrapper around API v1 — larger scope

Document the decision in an ADR before coding.

## CI gates (future)

- `release-macos.yml`: optional notarization step when secrets present
- Separate workflow for Play Store / PWA deploy once strategy is chosen