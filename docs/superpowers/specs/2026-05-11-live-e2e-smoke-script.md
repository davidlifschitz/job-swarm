# Live E2E smoke script design

## Goal

Give agents and operators a repeatable command that proves the website can do a
real no-credentials E2E workflow against live public data.

## Problem

The live Anthropic Greenhouse browser smoke is currently an ad hoc sequence. It
proved the product works, but future agents cannot rerun it consistently or use
it as a regression gate.

## V1 Design

- Add `scripts/live_e2e_smoke.py`.
- The script creates a temporary DB, one reviewed public Anthropic Greenhouse
  seed, and a generated DOCX resume.
- It launches the FastAPI app through Uvicorn on a local free port.
- It drives Playwright through the actual browser workflow:
  1. upload DOCX resume
  2. create target profile
  3. refresh public source
  4. confirm live jobs were seen
  5. save a no-LLM job
  6. confirm Saved Jobs shows `Not reviewed`
  7. prepare the manual-submit packet
- It writes screenshots to the temp artifact directory and prints a small JSON
  summary.

## Safety

- No credentials.
- No LinkedIn or Indeed.
- No CAPTCHA/login bypass.
- No external application submission.
- Only GETs public employer/ATS job data and posts to the local app.

## Acceptance

- Unit tests cover the script's deterministic artifact helpers.
- Running the script locally completes the live workflow and prints
  `browser_e2e_ok`.
- README documents the command.
