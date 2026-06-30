from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Callable

import pytest
from fastapi.testclient import TestClient

from ml_job_swarm.app import create_app
from ml_job_swarm.ingest import AdapterRegistry, RefreshError
from ml_job_swarm.profile import create_target_profile


PREFERENCES = {
    "role": {"answer": "Machine Learning Engineer"},
    "level": {"answer": "senior"},
    "location": {"answer": "New York"},
    "work_mode": {"answer": "remote"},
    "company_stage": {"answer": "growth"},
}

KEYWORDS = {
    "desired_titles": ["Machine Learning Engineer"],
    "levels": ["senior"],
    "locations": ["New York"],
    "remote_modes": ["remote"],
    "company_stages": ["growth"],
}

SENSITIVE_SENTINELS = (
    "PRIVATE RESUME TEXT",
    "session=secret-token",
    "secret-api-key",
)


class FailingRefreshAdapter:
    def __init__(self):
        self.calls = []

    def fetch_jobs(self, source):
        self.calls.append(source)
        raise RefreshError(
            "blocked by source with session=secret-token",
            "blocked_response",
            status_code=403,
        )
@dataclass(frozen=True)
class ObservabilityGateCase:
    case_id: str
    action: Callable[[TestClient, object, int, int], None]
    expected_tables: tuple[str, ...]
    admin_paths: tuple[str, ...]


def _perform_refresh(client: TestClient, app, target_profile_id: int, job_id: int) -> None:
    app.state.adapter_registry = AdapterRegistry({"greenhouse": FailingRefreshAdapter()})
    response = client.post(
        "/dashboard/refresh-sources",
        data={"target_profile_id": str(target_profile_id)},
        follow_redirects=False,
    )
    assert response.status_code == 303


def _perform_save_job(client: TestClient, _app, target_profile_id: int, job_id: int) -> None:
    response = client.post(
        f"/jobs/{job_id}/decision",
        data={
            "target_profile_id": str(target_profile_id),
            "decision": "saved",
            "notes": "shortlist note with secret-api-key",
            "return_to": f"/dashboard?target_profile_id={target_profile_id}",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303


def _perform_packet_prep(
    client: TestClient, _app, target_profile_id: int, job_id: int
) -> None:
    response = client.post(
        f"/jobs/{job_id}/decision",
        data={
            "target_profile_id": str(target_profile_id),
            "decision": "saved",
            "notes": "prepare packet",
            "return_to": f"/dashboard?target_profile_id={target_profile_id}",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    packet = client.post(
        f"/jobs/{job_id}/application-packet",
        data={"target_profile_id": str(target_profile_id)},
        follow_redirects=False,
    )
    assert packet.status_code == 303


OBSERVABILITY_GATE_CASES = [
    ObservabilityGateCase(
        case_id="refresh",
        action=_perform_refresh,
        expected_tables=("ingestion_runs", "source_friction_events"),
        admin_paths=("/admin/runs", "/admin/sources/friction"),
    ),
    ObservabilityGateCase(
        case_id="save_job",
        action=_perform_save_job,
        expected_tables=("job_decisions",),
        admin_paths=("/admin/audit",),
    ),
    ObservabilityGateCase(
        case_id="packet_prep",
        action=_perform_packet_prep,
        expected_tables=("application_packets",),
        admin_paths=("/admin/audit",),
    ),
]


@pytest.mark.parametrize(
    "case",
    OBSERVABILITY_GATE_CASES,
    ids=[case.case_id for case in OBSERVABILITY_GATE_CASES],
)
def test_operator_observability_gate_matrix(case: ObservabilityGateCase):
    app = create_app()
    target_profile_id, job_id = _seed_profile_job_and_source(app)
    _seed_private_resume_section(app.state.conn, target_profile_id)
    client = TestClient(app)

    case.action(client, app, target_profile_id, job_id)

    for table in case.expected_tables:
        count = app.state.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        assert count >= 1, f"{case.case_id}: expected rows in {table}"

    _assert_timestamped_records(app.state.conn, case)

    for admin_path in case.admin_paths:
        response = client.get(admin_path)
        assert response.status_code == 200
        _assert_no_secrets_in_text(response.text, case.case_id, admin_path)

    _assert_stored_payloads_redacted(app.state.conn, case)


def _assert_timestamped_records(conn, case: ObservabilityGateCase) -> None:
    if "ingestion_runs" in case.expected_tables:
        row = conn.execute(
            "SELECT started_at, finished_at FROM ingestion_runs ORDER BY id DESC LIMIT 1"
        ).fetchone()
        assert row["started_at"]
        assert row["finished_at"]

    if "source_friction_events" in case.expected_tables:
        row = conn.execute(
            "SELECT created_at FROM source_friction_events ORDER BY id DESC LIMIT 1"
        ).fetchone()
        assert row["created_at"]

    if "job_decisions" in case.expected_tables:
        row = conn.execute(
            "SELECT updated_at FROM job_decisions ORDER BY id DESC LIMIT 1"
        ).fetchone()
        assert row["updated_at"]

    if "application_packets" in case.expected_tables:
        row = conn.execute(
            "SELECT updated_at FROM application_packets ORDER BY id DESC LIMIT 1"
        ).fetchone()
        assert row["updated_at"]


def _assert_stored_payloads_redacted(conn, case: ObservabilityGateCase) -> None:
    if "source_friction_events" in case.expected_tables:
        row = conn.execute(
            "SELECT details_json FROM source_friction_events ORDER BY id DESC LIMIT 1"
        ).fetchone()
        details = json.loads(row["details_json"])
        assert "event_type" in details
        assert "error" in details

    if "application_packets" in case.expected_tables:
        row = conn.execute(
            "SELECT packet_json FROM application_packets ORDER BY id DESC LIMIT 1"
        ).fetchone()
        packet_text = row["packet_json"]
        for sentinel in SENSITIVE_SENTINELS:
            assert sentinel not in packet_text, (
                f"packet_json leaked {sentinel!r} for {case.case_id}"
            )


def _assert_no_secrets_in_text(text: str, case_id: str, path: str) -> None:
    for sentinel in SENSITIVE_SENTINELS:
        assert sentinel not in text, (
            f"{case_id}: {path} leaked sensitive value {sentinel!r}"
        )


def _seed_profile_job_and_source(app) -> tuple[int, int]:
    conn = app.state.conn
    target_profile_id = _seed_profile(conn)
    company_id = conn.execute(
        """
        INSERT INTO companies (name, normalized_name, stage)
        VALUES (?, ?, ?)
        """,
        ("Example AI", "example ai", "growth"),
    ).lastrowid
    conn.execute(
        """
        INSERT INTO job_sources (
          company_id,
          url,
          source_type,
          policy_mode,
          review_status
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            company_id,
            "https://boards.greenhouse.io/example",
            "greenhouse",
            "allowed",
            "reviewed",
        ),
    )
    job_id = conn.execute(
        """
        INSERT INTO jobs (
          company_id,
          external_id,
          title,
          department,
          location_text,
          remote_mode,
          employment_type,
          seniority,
          description_text,
          requirements_text,
          apply_url,
          source_url,
          content_hash
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            company_id,
            "observability-gate-job",
            "Senior Machine Learning Engineer",
            "Engineering",
            "Remote - New York, NY",
            "remote",
            "Full-time",
            "senior",
            "Build ML ranking systems with Python and PyTorch.",
            "Python, PyTorch, and model serving.",
            "https://boards.greenhouse.io/example/jobs/1",
            "https://boards.greenhouse.io/example/jobs/1",
            "observability-gate-hash",
        ),
    ).lastrowid
    conn.commit()
    return target_profile_id, int(job_id)


def _seed_profile(conn) -> int:
    resume_asset_id = conn.execute(
        """
        INSERT INTO resume_assets (original_filename, content_type, storage_path, sha256)
        VALUES (?, ?, ?, ?)
        """,
        ("resume.pdf", "application/pdf", "/tmp/resume.pdf", "observability-gate-sha"),
    ).lastrowid
    return create_target_profile(
        conn,
        resume_asset_id=resume_asset_id,
        keywords=KEYWORDS,
        preferences=PREFERENCES,
    )


def _seed_private_resume_section(conn, target_profile_id: int) -> None:
    resume_asset_id = conn.execute(
        """
        SELECT resume_asset_id
        FROM target_profiles
        WHERE id = ?
        """,
        (target_profile_id,),
    ).fetchone()["resume_asset_id"]
    parse_run_id = conn.execute(
        """
        INSERT INTO resume_parse_runs (
          resume_asset_id,
          parser,
          parser_version,
          status,
          confidence
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (resume_asset_id, "test", "v1", "succeeded", 1.0),
    ).lastrowid
    conn.execute(
        """
        INSERT INTO resume_sections (
          parse_run_id,
          section_type,
          heading,
          text,
          sort_order
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            parse_run_id,
            "experience",
            "Experience",
            "PRIVATE RESUME TEXT for observability gate",
            1,
        ),
    )
    conn.commit()
