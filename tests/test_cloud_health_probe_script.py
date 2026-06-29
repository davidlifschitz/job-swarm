from __future__ import annotations

import json
import math
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "cloud-health-probe.sh"


def compute_p95_ms(latencies_ms: list[int]) -> int:
    """Nearest-rank p95 used by scripts/cloud-health-probe.sh."""
    if not latencies_ms:
        raise ValueError("no latency samples")
    values = sorted(latencies_ms)
    index = max(0, min(math.ceil(0.95 * len(values)) - 1, len(values) - 1))
    return values[index]


def extract_health_p95_threshold(
    health_payload: dict[str, object],
    *,
    fallback_ms: int = 200,
) -> int:
    slo_targets = health_payload.get("slo_targets")
    if not isinstance(slo_targets, dict):
        return fallback_ms
    threshold = slo_targets.get("health_p95_ms", fallback_ms)
    return int(threshold)


def _free_port(host: str = "127.0.0.1") -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return int(sock.getsockname()[1])


def _wait_for_healthz(base_url: str, *, timeout_seconds: float = 15.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"{base_url}/healthz", timeout=2) as response:
                if response.status == 200:
                    return
        except (urllib.error.URLError, TimeoutError) as exc:
            last_error = exc
        time.sleep(0.1)
    raise RuntimeError(f"App did not become healthy at {base_url}: {last_error}")


def test_compute_p95_ms_uses_nearest_rank_percentile():
    assert compute_p95_ms([100, 110, 120, 130, 140, 150, 160, 170, 180, 190]) == 190
    assert (
        compute_p95_ms([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20])
        == 19
    )


def test_extract_health_p95_threshold_reads_slo_targets_or_fallback():
    assert extract_health_p95_threshold({"slo_targets": {"health_p95_ms": 150}}) == 150
    assert extract_health_p95_threshold({"slo_targets": {}}) == 200
    assert extract_health_p95_threshold({}) == 200


def test_cloud_health_probe_script_passes_against_local_app(tmp_path):
    db_path = tmp_path / "health-probe.db"
    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"
    env = os.environ.copy()
    env["ML_JOB_SWARM_DB_PATH"] = str(db_path)

    server = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "ml_job_swarm.app:create_app_from_env",
            "--factory",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    try:
        _wait_for_healthz(base_url)
        health = json.loads(
            urllib.request.urlopen(f"{base_url}/healthz", timeout=2).read().decode("utf-8")
        )
        result = subprocess.run(
            ["bash", str(SCRIPT_PATH)],
            check=False,
            capture_output=True,
            text=True,
            env={**env, "BASE_URL": base_url, "PROBE_COUNT": "10"},
        )
    finally:
        if server.poll() is None:
            server.terminate()
            try:
                server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=5)

    assert result.returncode == 0, result.stderr or result.stdout
    summary = result.stdout.strip().splitlines()[-1]
    assert "health_p95_ms=" in summary
    assert "threshold=200" in summary
    assert "probes=10" in summary
    assert "pass=true" in summary
    assert extract_health_p95_threshold(health) == 200
