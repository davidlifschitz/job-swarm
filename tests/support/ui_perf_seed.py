from __future__ import annotations

from dataclasses import dataclass

from ml_job_swarm.profile import create_target_profile

DEFAULT_JOB_COUNT = 500
DEFAULT_SOURCE_COUNT = 50
DEFAULT_SAVED_JOB_COUNT = 50

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

SOURCE_TYPES = ("greenhouse", "lever")


@dataclass(frozen=True)
class UiPerfSeedResult:
    target_profile_id: int
    sample_job_id: int
    job_count: int
    source_count: int
    saved_job_count: int


def seed_ui_perf_db(
    conn,
    *,
    job_count: int = DEFAULT_JOB_COUNT,
    source_count: int = DEFAULT_SOURCE_COUNT,
    saved_job_count: int = DEFAULT_SAVED_JOB_COUNT,
) -> UiPerfSeedResult:
    if job_count < 1:
        raise ValueError("job_count must be at least 1")
    if source_count < 1:
        raise ValueError("source_count must be at least 1")
    if saved_job_count < 0:
        raise ValueError("saved_job_count must be non-negative")

    resume_asset_id = conn.execute(
        """
        INSERT INTO resume_assets (original_filename, content_type, storage_path, sha256)
        VALUES (?, ?, ?, ?)
        """,
        (
            "ui-perf-resume.pdf",
            "application/pdf",
            "/tmp/ui-perf-resume.pdf",
            "ui-perf-resume-sha",
        ),
    ).lastrowid
    target_profile_id = create_target_profile(
        conn,
        resume_asset_id=resume_asset_id,
        keywords=KEYWORDS,
        preferences=PREFERENCES,
    )

    company_ids: list[int] = []
    source_ids: list[int] = []
    for index in range(source_count):
        slug = f"ui-perf-co-{index:02d}"
        company_id = conn.execute(
            """
            INSERT INTO companies (name, normalized_name, stage)
            VALUES (?, ?, ?)
            """,
            (f"UI Perf Co {index:02d}", slug, "growth"),
        ).lastrowid
        source_type = SOURCE_TYPES[index % len(SOURCE_TYPES)]
        source_id = conn.execute(
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
                f"https://boards.{source_type}.io/{slug}",
                source_type,
                "allowed",
                "reviewed",
            ),
        ).lastrowid
        company_ids.append(int(company_id))
        source_ids.append(int(source_id))

    jobs_per_source, remainder = divmod(job_count, source_count)
    job_rows: list[tuple] = []
    sample_job_id: int | None = None
    job_index = 0
    for source_index, (company_id, source_id) in enumerate(zip(company_ids, source_ids)):
        source_type = SOURCE_TYPES[source_index % len(SOURCE_TYPES)]
        slug = f"ui-perf-co-{source_index:02d}"
        count_for_source = jobs_per_source + (1 if source_index < remainder else 0)
        for offset in range(count_for_source):
            external_id = f"{slug}-job-{offset:03d}"
            job_rows.append(
                (
                    company_id,
                    source_id,
                    external_id,
                    "Senior Machine Learning Engineer",
                    "Engineering",
                    "Remote - New York, NY",
                    "remote",
                    "Full-time",
                    "senior",
                    "Build ML ranking systems with Python and PyTorch.",
                    "Python, PyTorch, and model serving.",
                    f"https://boards.{source_type}.io/{slug}/jobs/{offset}",
                    f"https://boards.{source_type}.io/{slug}/jobs/{offset}",
                    f"ui-perf-hash-{job_index:04d}",
                )
            )
            job_index += 1

    conn.executemany(
        """
        INSERT INTO jobs (
          company_id,
          job_source_id,
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
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        job_rows,
    )

    job_ids = [
        int(row["id"])
        for row in conn.execute("SELECT id FROM jobs ORDER BY id").fetchall()
    ]
    sample_job_id = job_ids[0]
    saved_count = min(saved_job_count, len(job_ids))
    if saved_count:
        conn.executemany(
            """
            INSERT INTO job_decisions (
              job_id,
              target_profile_id,
              decision,
              notes
            )
            VALUES (?, ?, 'saved', ?)
            """,
            [
                (job_id, target_profile_id, f"ui-perf saved job {job_id}")
                for job_id in job_ids[:saved_count]
            ],
        )

    conn.commit()

    actual_jobs = int(conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0])
    actual_sources = int(conn.execute("SELECT COUNT(*) FROM job_sources").fetchone()[0])
    assert actual_jobs == job_count, f"expected {job_count} jobs, got {actual_jobs}"
    assert actual_sources == source_count, (
        f"expected {source_count} sources, got {actual_sources}"
    )

    return UiPerfSeedResult(
        target_profile_id=int(target_profile_id),
        sample_job_id=int(sample_job_id),
        job_count=actual_jobs,
        source_count=actual_sources,
        saved_job_count=saved_count,
    )
