from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "notarize-macos-app.sh"

NOTARIZE_ENV_VARS = (
    "NOTARYTOOL_PROFILE",
    "APPLE_ID",
    "APPLE_APP_SPECIFIC_PASSWORD",
    "APPLE_TEAM_ID",
)


def _no_creds_env(app_path: Path) -> dict[str, str]:
    env = os.environ.copy()
    for name in NOTARIZE_ENV_VARS:
        env.pop(name, None)
    env["APP"] = str(app_path)
    return env


def _run_notarize(
    *args: str,
    app_path: Path,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(SCRIPT), *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        env=_no_creds_env(app_path),
    )


def test_notarize_macos_app_script_exists_and_is_executable():
    assert SCRIPT.is_file(), "notarize-macos-app.sh is missing"
    mode = SCRIPT.stat().st_mode
    assert mode & stat.S_IXUSR, "notarize-macos-app.sh is not executable"


def test_notarize_skips_without_credentials(tmp_path: Path):
    app_dir = tmp_path / "MLJobSwarm.app"
    app_dir.mkdir()

    result = _run_notarize(app_path=app_dir)
    combined = result.stdout + result.stderr
    assert result.returncode == 0, combined
    assert "Notarization skipped" in combined


def test_notarize_require_fails_without_credentials(tmp_path: Path):
    app_dir = tmp_path / "MLJobSwarm.app"
    app_dir.mkdir()

    result = _run_notarize("--require", app_path=app_dir)
    combined = result.stdout + result.stderr
    assert result.returncode == 1, combined
    assert "Notarization skipped" in combined
