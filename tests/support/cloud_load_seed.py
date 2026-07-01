from __future__ import annotations

import json
from dataclasses import dataclass

from ml_job_swarm.cloud_runtime import StoreConnection, create_run

DEFAULT_RUN_COUNT = 10


@dataclass(frozen=True)
class CloudLoadSeedResult:
    source_id: int
    profile_id: int
    run_ids: list[str]


def seed_cloud_load_catalog(conn: StoreConnection) -> tuple[int, int]:
    company_id = conn.execute(
        """
        INSERT INTO companies (name, normalized_name, ats_type, source_quality)
        VALUES ('Cloud Load Co', 'cloud load co', 'lever', 'reviewed')
        RETURNING id
        """
    ).fetchone()["id"]
    source_id = conn.execute(
        """
        INSERT INTO job_sources (
          company_id,
          url,
          source_type,
          policy_mode,
          review_status
        )
        VALUES (?, 'https://jobs.lever.co/cloud-load', 'lever', 'allowed', 'approved')
        RETURNING id
        """,
        (company_id,),
    ).fetchone()["id"]
    resume_asset_id = conn.execute(
        """
        INSERT INTO resume_assets (
          original_filename,
          content_type,
          storage_path,
          sha256
        )
        VALUES ('resume.pdf', 'application/pdf', '/tmp/cloud-load-resume.pdf', 'sha256-load')
        RETURNING id
        """
    ).fetchone()["id"]
    profile_id = conn.execute(
        """
        INSERT INTO target_profiles (
          resume_asset_id,
          name,
          desired_titles_json,
          levels_json,
          locations_json,
          remote_modes_json
        )
        VALUES (?, 'Cloud load profile', ?, ?, ?, ?)
        RETURNING id
        """,
        (
            resume_asset_id,
            json.dumps(["Machine Learning Engineer"]),
            json.dumps(["senior"]),
            json.dumps(["Remote"]),
            json.dumps(["remote"]),
        ),
    ).fetchone()["id"]
    seed_saved_packet_job(
        conn,
        company_id=int(company_id),
        source_id=int(source_id),
        profile_id=int(profile_id),
        external_id=f"{source_id}-cloud-load",
        apply_url="https://jobs.lever.co/cloud-load/cloud-load/apply",
        source_url="https://jobs.lever.co/cloud-load",
    )
    return int(source_id), int(profile_id)


def seed_saved_packet_job(
    conn: StoreConnection,
    *,
    company_id: int,
    source_id: int,
    profile_id: int,
    external_id: str,
    apply_url: str,
    source_url: str,
) -> int:
    job_id = conn.execute(
        """
        INSERT INTO jobs (
          company_id,
          job_source_id,
          external_id,
          title,
          location_text,
          remote_mode,
          seniority,
          description_text,
          requirements_text,
          apply_url,
          source_url,
          content_hash,
          status
        )
        VALUES (?, ?, ?, 'Senior Machine Learning Engineer', 'Remote', 'remote', 'senior',
                'Cloud packet seed.', 'Python.', ?, ?, ?, 'open')
        RETURNING id
        """,
        (company_id, source_id, external_id, apply_url, source_url, f"hash-{external_id}"),
    ).fetchone()["id"]
    conn.execute(
        """
        INSERT INTO job_decisions (job_id, target_profile_id, decision, notes)
        VALUES (?, ?, 'saved', 'cloud packet candidate')
        """,
        (job_id, profile_id),
    )
    conn.commit()
    return int(job_id)


def enqueue_cloud_load_runs(
    conn: StoreConnection,
    *,
    source_id: int,
    profile_id: int,
    run_count: int = DEFAULT_RUN_COUNT,
    user_id: str = "operator-1",
) -> list[str]:
    run_ids: list[str] = []
    for index in range(run_count):
        run = create_run(
            conn,
            user_id=user_id,
            requested_action="continue_local_workflow",
            input_manifest={
                "source_ids": [source_id],
                "target_profile_id": profile_id,
                "prepare_packets": True,
                "max_packets": 1,
            },
            environment_class="cloud",
            idempotency_key=f"cloud-load-{index}",
        )
        run_ids.append(str(run["id"]))
    return run_ids


def seed_cloud_load_db(
    conn: StoreConnection,
    *,
    run_count: int = DEFAULT_RUN_COUNT,
    user_id: str = "operator-1",
) -> CloudLoadSeedResult:
    source_id, profile_id = seed_cloud_load_catalog(conn)
    run_ids = enqueue_cloud_load_runs(
        conn,
        source_id=source_id,
        profile_id=profile_id,
        run_count=run_count,
        user_id=user_id,
    )
    return CloudLoadSeedResult(
        source_id=source_id,
        profile_id=profile_id,
        run_ids=run_ids,
    )
