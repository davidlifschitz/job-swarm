from ml_job_swarm.app import create_app
from ml_job_swarm.filtering import review_jobs_for_profile_resilient
from ml_job_swarm.profile import create_target_profile


class ExplodingClient:
    def review_fit(self, *args, **kwargs):
        raise RuntimeError("boom token secret")


def test_resilient_review_returns_failure_messages(tmp_path):
    app = create_app(tmp_path / "resilient-review.db")
    conn = app.state.conn
    resume_asset_id = conn.execute(
        """
        INSERT INTO resume_assets (original_filename, content_type, storage_path, sha256)
        VALUES ('resume.pdf', 'application/pdf', '/tmp/resume.pdf', 'digest-resilient')
        """
    ).lastrowid
    profile_id = create_target_profile(
        conn,
        resume_asset_id=resume_asset_id,
        keywords={
            "desired_titles": ["engineer"],
            "levels": ["senior"],
            "locations": ["remote"],
            "remote_modes": ["remote"],
            "company_stages": ["growth"],
        },
        preferences={
            "role": {"answer": "engineer"},
            "level": {"answer": "senior"},
            "location": {"answer": "remote"},
            "work_mode": {"answer": "remote"},
            "company_stage": {"answer": "growth"},
        },
    )
    company_id = conn.execute(
        "INSERT INTO companies (name, normalized_name, stage) VALUES ('Acme', 'acme', 'growth')"
    ).lastrowid
    conn.execute(
        """
        INSERT INTO jobs (company_id, external_id, title, source_url, content_hash, status)
        VALUES (?, '1', 'Engineer', 'https://example.com/jobs/1', 'hash-1', 'open')
        """,
        (company_id,),
    )
    conn.commit()

    result = review_jobs_for_profile_resilient(conn, profile_id, ExplodingClient())
    assert result.failures == 1
    assert result.failure_messages
    assert result.failure_messages[0] == "[redacted]"
