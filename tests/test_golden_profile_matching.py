from __future__ import annotations

import json
from pathlib import Path

from ml_job_swarm.filtering import rules_preview_jobs
from ml_job_swarm.profile import create_target_profile
from ml_job_swarm.resume_extract import parse_resume_text, record_parse_run
from ml_job_swarm.store import connect, init_db

FIXTURES = Path(__file__).parent / "fixtures"
GOLDEN_PROFILES = FIXTURES / "golden_profiles"
TOP_N = 20
MATCH_RATE_TARGET = 0.8


def test_golden_profile_top_twenty_match_rate_meets_threshold():
    fixture = _load_fixture("senior_ml_engineer_remote_nyc.json")
    conn, target_profile_id, job_lookup = _seed_fixture(fixture)

    previews = rules_preview_jobs(conn, target_profile_id, limit=TOP_N)

    assert previews, "expected rules preview to return ranked jobs for golden fixture"

    top_n = previews[:TOP_N]
    target = fixture["target"]
    matches = sum(
        1
        for preview in top_n
        if _job_matches_target(job_lookup[preview.job_id], target)
    )
    match_rate = matches / len(top_n)

    assert match_rate >= MATCH_RATE_TARGET, (
        f"top-{TOP_N} match rate {match_rate:.2f} below {MATCH_RATE_TARGET:.0%}; "
        f"matched {matches}/{len(top_n)}"
    )


def test_golden_profile_previews_expose_visible_match_reasons():
    fixture = _load_fixture("senior_ml_engineer_remote_nyc.json")
    conn, target_profile_id, _job_lookup = _seed_fixture(fixture)

    previews = rules_preview_jobs(conn, target_profile_id, limit=TOP_N)

    assert previews
    for preview in previews:
        assert preview.reasons or preview.risks, (
            f"preview for job_id={preview.job_id} title={preview.title!r} "
            "must include match signals or risks"
        )


def _load_fixture(name: str) -> dict:
    return json.loads((GOLDEN_PROFILES / name).read_text())


def _job_matches_target(job_fixture: dict, target: dict) -> bool:
    return (
        job_fixture["expected_role_family"] == target["role_family"]
        and job_fixture["expected_seniority_band"] == target["seniority_band"]
    )


def _seed_fixture(fixture: dict):
    conn = connect()
    init_db(conn)

    profile = fixture["profile"]
    resume_path = FIXTURES / profile["resume_fixture"]
    resume_text = resume_path.read_text()
    resume_asset_id = conn.execute(
        """
        INSERT INTO resume_assets (original_filename, content_type, storage_path, sha256)
        VALUES (?, ?, ?, ?)
        """,
        (
            resume_path.name,
            "text/plain",
            str(resume_path),
            f"golden-{fixture['name']}",
        ),
    ).lastrowid
    record_parse_run(conn, resume_asset_id, parse_resume_text(resume_text), None)

    target_profile_id = create_target_profile(
        conn,
        resume_asset_id=resume_asset_id,
        keywords=profile["keywords"],
        preferences=profile["preferences"],
    )

    company_ids: dict[str, int] = {}
    source_ids: dict[str, int] = {}
    job_lookup: dict[int, dict] = {}

    for job in fixture["jobs"]:
        company_name = job["company"]["name"]
        if company_name not in company_ids:
            company_ids[company_name] = conn.execute(
                """
                INSERT INTO companies (name, normalized_name, stage)
                VALUES (?, ?, ?)
                """,
                (
                    company_name,
                    company_name.lower(),
                    job["company"].get("stage"),
                ),
            ).lastrowid
            source_ids[company_name] = conn.execute(
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
                    company_ids[company_name],
                    f"https://boards.greenhouse.io/{company_name.lower().replace(' ', '-')}",
                    "greenhouse",
                    "allowed",
                    "reviewed",
                ),
            ).lastrowid

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
              content_hash
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                company_ids[company_name],
                source_ids[company_name],
                job["external_id"],
                job["title"],
                job["location_text"],
                job["remote_mode"],
                job["seniority"],
                job["description_text"],
                job["requirements_text"],
                f"https://boards.greenhouse.io/example/jobs/{job['external_id']}",
                f"https://boards.greenhouse.io/example/jobs/{job['external_id']}",
                f"hash-{job['external_id']}",
            ),
        ).lastrowid
        job_lookup[int(job_id)] = job

    conn.commit()
    return conn, target_profile_id, job_lookup
