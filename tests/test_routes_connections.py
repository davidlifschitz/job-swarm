from pathlib import Path

from fastapi.testclient import TestClient

from ml_job_swarm.app import create_app
from ml_job_swarm.profile import create_target_profile

FIXTURE_CSV = Path(__file__).parent / "fixtures" / "linkedin_connections.csv"

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


def test_connections_workspace_renders_import_form():
    app = create_app()
    client = TestClient(app)

    response = client.get("/connections")

    assert response.status_code == 200
    assert "LinkedIn connections" in response.text
    assert 'action="/connections/import"' in response.text
    assert "100% local processing" in response.text


def _seed_dataiku_match(conn):
    resume_asset_id = conn.execute(
        """
        INSERT INTO resume_assets (original_filename, content_type, storage_path, sha256)
        VALUES (?, ?, ?, ?)
        """,
        ("resume.pdf", "application/pdf", "/tmp/resume.pdf", "connections-route-sha"),
    ).lastrowid
    target_profile_id = create_target_profile(
        conn,
        resume_asset_id=resume_asset_id,
        keywords=KEYWORDS,
        preferences=PREFERENCES,
    )
    company_id = conn.execute(
        """
        INSERT INTO companies (name, normalized_name, stage)
        VALUES (?, ?, ?)
        """,
        ("Dataiku", "dataiku", "growth"),
    ).lastrowid
    conn.execute(
        """
        INSERT INTO jobs (
          company_id,
          external_id,
          title,
          source_url,
          content_hash,
          status
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            company_id,
            "dataiku-ml-engineer",
            "Senior ML Engineer",
            "https://boards.greenhouse.io/dataiku/jobs/1",
            "hash-dataiku-1",
            "open",
        ),
    )
    job_id = conn.execute("SELECT id FROM jobs").fetchone()["id"]
    conn.execute(
        """
        INSERT INTO fit_reviews (
          job_id,
          target_profile_id,
          fit_score,
          label,
          reasons_json,
          risks_json,
          recommendation,
          profile_version
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            job_id,
            target_profile_id,
            90,
            "Strong fit",
            '["Role and skills fit"]',
            "[]",
            "Prioritize",
            1,
        ),
    )
    conn.commit()
    return target_profile_id, job_id


def test_import_connections_csv_and_match_dashboard_companies():
    app = create_app()
    client = TestClient(app)
    target_profile_id, job_id = _seed_dataiku_match(app.state.conn)

    import_response = client.post(
        "/connections/import",
        files={
            "connections_file": (
                "Connections.csv",
                FIXTURE_CSV.read_bytes(),
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    assert import_response.status_code == 303
    assert "import_status=success" in import_response.headers["location"]

    dashboard = client.get(
        f"/dashboard?target_profile_id={target_profile_id}&connection_filter=with_connections"
    )
    assert dashboard.status_code == 200
    assert "Dataiku" in dashboard.text
    assert "Referral path" in dashboard.text
    assert "Jamie" in dashboard.text

    filtered_out = client.get(
        f"/dashboard?target_profile_id={target_profile_id}&connection_filter=with_connections"
    )
    assert "Dataiku" in filtered_out.text

    job_detail = client.get(
        f"/jobs/{job_id}?target_profile_id={target_profile_id}"
    )
    assert job_detail.status_code == 200
    assert "LinkedIn connections" in job_detail.text
    assert "Jamie Example" in job_detail.text
    assert "jamie-example-fixture" in job_detail.text


def test_import_connections_csv_rejects_invalid_file():
    app = create_app()
    client = TestClient(app)

    response = client.post(
        "/connections/import",
        files={"connections_file": ("bad.csv", b"name,title\n", "text/csv")},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert "import_status=invalid" in response.headers["location"]