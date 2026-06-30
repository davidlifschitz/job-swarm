from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "run-production-ops.sh"

OPS_ENV_VARS = (
    "DATABASE_URL",
    "ML_JOB_SWARM_SOURCE_DB",
    "ML_JOB_SWARM_DB_PATH",
    "ML_JOB_SWARM_RESUME_ASSET_DIR",
    "SUPABASE_PROJECT_REF",
    "SUPABASE_ACCESS_TOKEN",
    "NOTARYTOOL_PROFILE",
    "APPLE_ID",
    "APPLE_APP_SPECIFIC_PASSWORD",
    "APPLE_TEAM_ID",
    "CODESIGN_IDENTITY",
)


def _ci_like_env() -> dict[str, str]:
    """Environment without maintainer OPS credentials (typical CI)."""
    env = os.environ.copy()
    for name in OPS_ENV_VARS:
        env.pop(name, None)
    return env


def _run_script(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(SCRIPT), *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        env=env if env is not None else os.environ.copy(),
    )


def test_run_production_ops_script_exists_and_is_executable():
    assert SCRIPT.is_file(), "run-production-ops.sh is missing"
    mode = SCRIPT.stat().st_mode
    assert mode & stat.S_IXUSR, "run-production-ops.sh is not executable"


def test_run_production_ops_check_env_fails_without_credentials():
    result = _run_script("--check-env", env=_ci_like_env())
    combined = result.stdout + result.stderr
    assert result.returncode == 1, combined
    assert "OPS-1" in combined
    assert "DATABASE_URL" in combined
    assert "ML_JOB_SWARM_SOURCE_DB" in combined
    assert "Environment preflight: BLOCKED" in combined


def test_run_production_ops_dry_run_succeeds():
    result = _run_script("--dry-run")
    combined = result.stdout + result.stderr
    assert result.returncode == 0, combined
    assert "All local ops-readiness checks passed." in result.stdout


def test_run_production_ops_help_lists_subcommands():
    result = _run_script("--help")
    combined = result.stdout + result.stderr
    assert result.returncode == 0, combined
    for flag in ("--ops-1", "--ops-2", "--ops-3", "--check-env", "--dry-run"):
        assert flag in combined, f"expected {flag} in help output"
