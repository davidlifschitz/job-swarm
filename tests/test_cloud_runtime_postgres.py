import os

import pytest

from ml_job_swarm.cloud_runtime import create_run, get_run, list_run_events
from ml_job_swarm.cloud_worker import run_cloud_workflow_once
from ml_job_swarm.db.factory import connect_from_env
from ml_job_swarm.db.postgres_backend import PostgresDatabase
from ml_job_swarm.store import init_db

POSTGRES_URL = os.environ.get("ML_JOB_SWARM_TEST_DATABASE_URL", "")

pytestmark = pytest.mark.skipif(
    not POSTGRES_URL,
    reason="Set ML_JOB_SWARM_TEST_DATABASE_URL to run Postgres cloud runtime tests",
)


@pytest.fixture
def postgres_conn(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", POSTGRES_URL)
    db = connect_from_env()
    assert isinstance(db, PostgresDatabase)
    init_db(db)
    db.execute("DELETE FROM cloud_run_events")
    db.execute("DELETE FROM cloud_runs")
    db.commit()
    yield db
    db.close()


def test_postgres_create_run_persists_lifecycle_state(postgres_conn):
    run = create_run(
        postgres_conn,
        user_id="operator-1",
        requested_action="refresh_source",
        input_manifest={"sources": ["https://jobs.lever.co/acme/123"]},
        idempotency_key="postgres-runtime",
    )

    persisted = get_run(postgres_conn, run["id"])
    assert persisted["status"] == "queued"
    assert persisted["user_id"] == "operator-1"
    assert persisted["input_manifest"] == {
        "sources": ["https://jobs.lever.co/acme/123"]
    }
    assert [event["event_type"] for event in list_run_events(postgres_conn, run["id"])] == [
        "run_created"
    ]


def test_postgres_worker_claims_queued_run(postgres_conn):
    run = create_run(
        postgres_conn,
        user_id="operator-1",
        requested_action="refresh_source",
        input_manifest={"sources": ["https://www.linkedin.com/jobs/view/1"]},
    )

    result = run_cloud_workflow_once(postgres_conn, adapter_registry=_EmptyRegistry())

    assert result["run_id"] == run["id"]
    assert result["status"] == "waiting_for_user"


class _EmptyRegistry:
    def source_types(self):
        return ()

    def adapter_for(self, source_type: str):
        raise KeyError(source_type)