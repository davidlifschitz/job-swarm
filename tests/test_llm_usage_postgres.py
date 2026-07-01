import os

import pytest

from ml_job_swarm.llm import llm_usage_summary
from ml_job_swarm.store import init_db, open_store_connection


@pytest.mark.skipif(
    not os.environ.get("ML_JOB_SWARM_TEST_DATABASE_URL"),
    reason="Postgres test database URL not configured",
)
def test_llm_usage_summary_on_postgres():
    conn = open_store_connection()
    init_db(conn)
    summary = llm_usage_summary(conn)
    assert "requests_today" in summary
    assert "total_requests" in summary
