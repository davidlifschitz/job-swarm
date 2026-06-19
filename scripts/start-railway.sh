#!/usr/bin/env bash
set -euo pipefail

case "${ML_JOB_SWARM_PROCESS:-web}" in
  worker)
    exec ./scripts/start-cloud-worker.sh
    ;;
  *)
    exec ./scripts/start-hosted.sh
    ;;
esac