from __future__ import annotations

import math
import os
import time

import pytest
from fastapi.testclient import TestClient

from ml_job_swarm.app import create_app
from tests.support.ui_perf_seed import seed_ui_perf_db
from tests.test_cloud_health_probe_script import compute_p95_ms

SAMPLE_COUNT = 10
DEFAULT_P95_THRESHOLD_MS = 1000


def _p95_threshold_ms() -> int:
    return int(os.environ.get("ML_JOB_SWARM_UI_PERF_P95_MS", DEFAULT_P95_THRESHOLD_MS))


def _measure_get_p95_ms(client: TestClient, path: str, *, samples: int = SAMPLE_COUNT) -> int:
    warmup = client.get(path)
    assert warmup.status_code == 200, f"warmup GET {path} returned {warmup.status_code}"

    latencies_ms: list[int] = []
    for _ in range(samples):
        started = time.perf_counter()
        response = client.get(path)
        elapsed_ms = int(math.ceil((time.perf_counter() - started) * 1000))
        assert response.status_code == 200, f"GET {path} returned {response.status_code}"
        latencies_ms.append(elapsed_ms)
    return compute_p95_ms(latencies_ms)


@pytest.mark.skipif(
    os.environ.get("ML_JOB_SWARM_SKIP_UI_PERF") == "1",
    reason="UI performance gate skipped via ML_JOB_SWARM_SKIP_UI_PERF=1",
)
def test_ui_render_p95_stays_within_threshold_with_seeded_catalog(tmp_path):
    app = create_app(tmp_path / "ui-perf-gate.db")
    seed = seed_ui_perf_db(app.state.conn)
    client = TestClient(app)
    threshold_ms = _p95_threshold_ms()

    routes = {
        "dashboard": f"/dashboard?target_profile_id={seed.target_profile_id}",
        "job_detail": (
            f"/jobs/{seed.sample_job_id}?target_profile_id={seed.target_profile_id}"
        ),
        "saved_jobs": f"/dashboard/saved?target_profile_id={seed.target_profile_id}",
        "admin_sources": "/admin/sources",
    }

    observed: dict[str, int] = {}
    for label, path in routes.items():
        observed[label] = _measure_get_p95_ms(client, path)

    violations = [
        f"{label} p95={observed[label]}ms exceeds {threshold_ms}ms"
        for label in routes
        if observed[label] > threshold_ms
    ]
    assert not violations, (
        "UI render p95 gate failed:\n"
        + "\n".join(violations)
        + "\nObserved p95 (ms): "
        + ", ".join(f"{label}={value}" for label, value in observed.items())
    )
