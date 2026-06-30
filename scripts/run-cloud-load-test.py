#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    repo_root = Path(__file__).resolve().parents[1]
    command = [
        sys.executable,
        "-m",
        "pytest",
        "tests/test_cloud_load_capacity.py",
        "-q",
    ]
    if argv:
        command.extend(argv)
    completed = subprocess.run(command, cwd=repo_root, check=False)
    return int(completed.returncode)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
