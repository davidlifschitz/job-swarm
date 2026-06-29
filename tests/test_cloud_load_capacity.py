from __future__ import annotations

from ml_job_swarm.cloud_runtime import get_run
from ml_job_swarm.cloud_worker import run_cloud_worker_loop
from ml_job_swarm.ingest import AdapterRegistry, RawJob
from ml_job_swarm.store import connect, init_db
from tests.support.cloud_load_seed import DEFAULT_RUN_COUNT, seed_cloud_load_db


class FakeLoadAdapter:
    def fetch_jobs(self, source):
        return [
            RawJob(
                external_id=f"{source.id}-cloud-load",
                title="Senior Machine Learning Engineer",
                location_text="Remote",
                remote_mode="remote",
                seniority="senior",
                description_text="Cloud load capacity test.",
                requirements_text="Python, ML, cloud runtime.",
                apply_url=f"{source.url}/cloud-load/apply",
                source_url=source.url,
            )
        ]


def test_cloud_load_capacity_drains_runs_without_duplicate_packets(tmp_path):
    conn = connect(tmp_path / "cloud-load-capacity.db")
    init_db(conn)
    seed = seed_cloud_load_db(conn, run_count=DEFAULT_RUN_COUNT)

    summary = run_cloud_worker_loop(
        conn,
        adapter_registry=AdapterRegistry({"lever": FakeLoadAdapter()}),
        max_runs=DEFAULT_RUN_COUNT + 5,
    )

    assert summary["runs_processed"] == DEFAULT_RUN_COUNT
    assert summary["idle"] is True
    assert (
        conn.execute(
            "SELECT COUNT(*) AS count FROM cloud_runs WHERE status = 'queued'"
        ).fetchone()["count"]
        == 0
    )

    for run_id in seed.run_ids:
        run = get_run(conn, run_id)
        assert run["status"] == "waiting_for_user"
        assert run["next_action"] == "manual_final_submit"

    packet_count = conn.execute(
        "SELECT COUNT(*) AS count FROM application_packets"
    ).fetchone()["count"]
    unique_packet_pairs = conn.execute(
        """
        SELECT COUNT(*) AS count
        FROM (
          SELECT job_id, target_profile_id
          FROM application_packets
          GROUP BY job_id, target_profile_id
        )
        """
    ).fetchone()["count"]

    assert packet_count == unique_packet_pairs
    assert packet_count == 1
    assert (
        conn.execute("SELECT COUNT(*) AS count FROM jobs").fetchone()["count"] == 1
    )
