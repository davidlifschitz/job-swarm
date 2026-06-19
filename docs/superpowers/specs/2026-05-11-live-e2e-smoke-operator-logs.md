# Live E2E smoke operator logs

## Goal

Make the live browser smoke command debuggable when it is used as an operator
regression check.

## Problem

The smoke script launches Uvicorn as a child process. If server output is held
in an unconsumed pipe, a noisy run can hang and a failed run leaves no obvious
server log next to the screenshots and generated DB.

## V1 Design

- Write Uvicorn output to `uvicorn.log` inside the smoke artifact directory.
- Include `server_log_path` in the successful JSON summary.
- Print the artifact directory to stderr before the browser workflow begins so
  failure cases still expose where screenshots, DB, seed, resume, and logs live.
- Keep the smoke command stdout machine-readable JSON on success.

## Safety

- No new live actions are introduced.
- The command remains limited to public employer/ATS data and local app posts.
- Server logs stay in the local artifact directory and are not committed.

## Acceptance

- A unit test proves `_start_server` routes Uvicorn output to the artifact log
  and closes the log handle during cleanup.
- The focused smoke-script tests pass.
- The full suite passes.
- The live smoke command still completes and reports `browser_e2e_ok`.
