import json
import os
import subprocess
import sys

import pytest


@pytest.mark.skipif(
    not os.environ.get("ML_JOB_SWARM_TEST_DATABASE_URL"),
    reason="Postgres test database URL not configured",
)
def test_cli_refresh_accepts_database_url(tmp_path, monkeypatch):
    monkeypatch.setenv(
        "DATABASE_URL",
        os.environ["ML_JOB_SWARM_TEST_DATABASE_URL"],
    )
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "ml_job_swarm.cli",
            "refresh",
            "--public-ats",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode in {0, 1}, result.stderr
    assert result.stdout.strip(), result.stderr
    payload = json.loads(result.stdout)
    assert "sources_attempted" in payload
