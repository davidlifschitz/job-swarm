#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

if command -v uv >/dev/null 2>&1; then
  exec uv run pytest tests/test_cloud_runtime_parity_fixtures.py -q "$@"
fi

exec python3 -m pytest tests/test_cloud_runtime_parity_fixtures.py -q "$@"
