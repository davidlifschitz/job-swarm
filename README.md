# ml-job-swarm

Local-first job catalog and resume matching for curated technical roles.

This rebuild starts from the V1 foundation:

- curated company catalog and public career sources
- resume/profile extraction with explicit consent boundaries
- rules-first filtering before LLM fit review
- local SQLite persistence
- grouped company-first job results
- admin visibility for source friction
- **macOS native app** (SwiftUI) with the same Python backend

## Install ML Job Swarm (macOS)

Prebuilt app for **Apple Silicon, macOS 14+**.

All releases: [GitHub Releases](https://github.com/davidlifschitz/job-swarm/releases)

### Homebrew (recommended)

Requires [Homebrew](https://brew.sh).

```bash
brew tap davidlifschitz/job-swarm https://github.com/davidlifschitz/job-swarm
brew trust davidlifschitz/job-swarm
brew install --cask ml-job-swarm
```

Upgrade later with `brew upgrade --cask ml-job-swarm`.

Optional: submit the cask to [homebrew-cask](https://github.com/Homebrew/homebrew-cask) so users can run `brew install --cask ml-job-swarm` without adding a tap.

### Terminal installer (fallback)

This build is **not Apple-notarized**. Browser downloads may trigger Gatekeeper; the installer clears quarantine and re-signs the app.

**1. Download** the `.tar.gz` to `~/Downloads`:

```bash
curl -L -o ~/Downloads/MLJobSwarm-0.2.1-macos-arm64.tar.gz \
  https://github.com/davidlifschitz/job-swarm/releases/download/v0.2.1/MLJobSwarm-0.2.1-macos-arm64.tar.gz
```

**2. Run the installer** (pick one):

*No git clone needed:*

```bash
curl -fsSL -o /tmp/install-mljobswarm.sh \
  https://raw.githubusercontent.com/davidlifschitz/job-swarm/main/scripts/install-macos-release.sh

bash /tmp/install-mljobswarm.sh ~/Downloads/MLJobSwarm-0.2.1-macos-arm64.tar.gz
```

*If you already cloned this repo:*

```bash
./scripts/install-macos-release.sh ~/Downloads/MLJobSwarm-0.2.1-macos-arm64.tar.gz
```

The installer extracts the archive, copies to `~/Applications/MLJobSwarm.app`, clears quarantine, re-signs the app, and launches it.

**3. Launch later** from Applications or Spotlight (`ML Job Swarm`).

### If the app itself is blocked on launch

```bash
xattr -cr ~/Applications/MLJobSwarm.app
codesign --force --deep --sign - ~/Applications/MLJobSwarm.app
open ~/Applications/MLJobSwarm.app
```

Or right-click the app → **Open** → **Open**. You may also see **System Settings → Privacy & Security → Open Anyway** after the first blocked attempt.

### Avoid Gatekeeper entirely

Build locally (no browser quarantine):

```bash
uv sync
chmod +x scripts/build-macos-app.sh
./scripts/build-macos-app.sh
open ~/Applications/MLJobSwarm.app
```

The release artifact bundles its own Python virtualenv. [uv](https://docs.astral.sh/uv/) is only required when building from source.

**Maintainers:** Tier 1 distribution is complete — see [docs/tier1-macos-release.md](docs/tier1-macos-release.md) and [docs/product-tiers.md](docs/product-tiers.md). Tag `v*.*.*` on `main` to publish a new macOS release and bump the Homebrew cask.

## Run Locally (web)

```bash
uv sync
ML_JOB_SWARM_DB_PATH=jobs.db \
ML_JOB_SWARM_SEED_COMPANIES=data/seed_companies.json \
uv run --with uvicorn uvicorn 'ml_job_swarm.app:create_app_from_env' --factory --host 127.0.0.1 --port 8765
```

Then open:

- `http://127.0.0.1:8765/onboarding`
- `http://127.0.0.1:8765/dashboard`
- `http://127.0.0.1:8765/connections`
- `http://127.0.0.1:8765/admin/sources`

## macOS app (SwiftUI)

Native desktop shell in `macos/MLJobSwarm`. It launches the bundled Python backend locally and talks to `/api/v1/*`.

Install from a GitHub release: see **Install ML Job Swarm (macOS)** above.

`./scripts/run-macos-app.sh` is for terminal dev only (not installed to Applications).

See `macos/README.md` for architecture, LLM settings, and snapshot testing.

### macOS features (v0.2.1)

- Dashboard with referral network, filter chips, and careers refresh
- LinkedIn connections import and catalog matching
- LLM settings with Keychain storage, live usage dashboard, and optional legacy `.env` one-time import (local only)
- Source health with refresh-all
- Saved jobs, job detail, onboarding, and admin source health

The runtime app uses a persistent SQLite database at `~/Library/Application Support/MLJobSwarm/jobs.db` and idempotently imports the reviewed seed company catalog.

## Privacy and what stays local

**Never committed to this repository:**

- `.env` files and API keys (`OPENROUTER_API_KEY`, Telegram tokens, etc.)
- `jobs.db` or any user SQLite database
- LinkedIn export CSVs with real contacts (tests use fictional fixture names only)
- macOS Keychain entries or `~/Library/Application Support/MLJobSwarm/` runtime data
- Resume files uploaded through onboarding

**Local-only by design:**

- OpenRouter API keys in the macOS app are stored in Keychain and injected into the bundled backend process on your machine
- LLM audit metadata stores request hashes, not raw resume text or prompts

Before contributing, run `git status` and confirm you are not staging `.env`, `jobs.db`, `macos/dist/`, or personal exports.

## Deployment Status

No hosted production URL is declared in this repo's GitHub homepage or deployment
metadata right now, so the website reports `Deployment: Local development` by
default. Set `ML_JOB_SWARM_PUBLIC_URL` when a real hosted app exists; `PUBLIC_URL`
is the fallback explicit URL. If neither is set, the shell detects provider
variables in this order: `RENDER_EXTERNAL_URL`, `VERCEL_URL`,
`RAILWAY_PUBLIC_DOMAIN`, then `FLY_APP_NAME`.

Seeded company/source rows are real local catalog data for development and
first-run testing. They are not presented as production job results until source
refresh and match review have run.

## V1 Flow

1. Upload a PDF or DOCX resume.
2. The local parser extracts sections and keywords.
3. Low-confidence parses show a consent prompt before any configured vision
   fallback provider can receive resume-derived content.
4. Answer the fixed preference questions for role, level, location, work mode,
   and company stage.
5. Results are grouped by company. Mismatch-risk jobs are hidden under each
   company by default.
6. Admin source health shows friction events, source status, and safe exports.

OpenRouter calls are behind strict schemas and are mocked in tests. LLM metadata
stores request hashes and input references, not raw private prompts, raw resume
text, cookies, or browser profiles.

## Runtime LLM Configuration

The web app configures real OpenRouter clients only when `OPENROUTER_API_KEY` is
present. Without it, LLM-triggering routes keep returning the existing disabled
client responses.

On macOS, configure the key in **LLM settings** inside the app (stored in Keychain).

Optional environment variables:

- `OPENROUTER_BASE_URL`
- `OPENROUTER_FIT_MODEL`
- `OPENROUTER_RESUME_REWRITE_MODEL`
- `OPENROUTER_VISION_MODEL`
- `OPENROUTER_HTTP_REFERER`
- `OPENROUTER_APP_TITLE`

The default model is `openrouter/auto`; set per-feature model variables when you
want tighter cost, latency, or modality control.

## Development

Product readiness tracking lives in
`docs/superpowers/e2e-product-readiness.md`; active and completed implementation
plans are indexed in `docs/superpowers/plans/README.md`.

```bash
uv run pytest
uv run pytest tests/test_api_v1.py tests/test_api_v1_llm.py tests/test_routes_connections.py -q
```

Cron-friendly public ATS refresh:

```bash
uv run ml-job-swarm refresh --public-ats --db jobs.db --seed data/seed_companies.json
```

Public refresh uses reviewed seed sources, source-policy checks, and the built-in
public ATS adapters. Unsupported reviewed source types are skipped and reported
as `sources_skipped`. If a supported source fails, the command records source
friction and exits nonzero so a cron runner can alert on catalog drift.

Deterministic fixture refresh for tests and local development:

```bash
uv run ml-job-swarm refresh --db jobs.db --seed data/seed_companies.json --fixture-dir tests/fixtures
```

Fixture refresh skips reviewed source types that do not have a matching
`<source_type>_jobs.json` file and reports `sources_skipped`.

Live no-credentials browser smoke against a temporary DB and one public
Anthropic Greenhouse seed:

```bash
uv run --with uvicorn --with playwright python scripts/live_e2e_smoke.py
```

The smoke uploads a generated DOCX resume, creates a target profile, refreshes
public source data, saves a no-LLM job, and prepares a local manual-submit
packet. It prints progress and the artifact directory to stderr, writes
screenshots plus `uvicorn.log` to that directory, and never submits an external
application.

V1 does not scrape LinkedIn or Indeed, bypass CAPTCHA/login flows, use hidden
browser sessions, or submit applications. The macOS app uses HTTP adapters for
public careers pages and ATS APIs; browser automation exists only under `Legacy/`.