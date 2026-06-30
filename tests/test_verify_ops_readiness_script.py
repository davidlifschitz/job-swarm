from __future__ import annotations

import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "verify-ops-readiness.sh"


def test_verify_ops_readiness_script_passes_locally():
    assert SCRIPT.is_file(), "verify-ops-readiness.sh is missing"
    result = subprocess.run(
        ["bash", str(SCRIPT)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "All local ops-readiness checks passed." in result.stdout
    assert "Product gate tests" in result.stdout or "==> Product gate tests" in result.stdout
