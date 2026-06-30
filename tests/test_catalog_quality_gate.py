from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from ml_job_swarm.cli import main as cli_main
from ml_job_swarm.product_goals import catalog_quality_metrics
from ml_job_swarm.store import connect

FIXTURES = Path(__file__).parent / "fixtures"
FIXED_NOW = datetime(2026, 6, 29, 12, 0, tzinfo=timezone.utc)
TARGET_DUPLICATE_RATE_MAX = 0.02


def assert_catalog_quality_gate(
    jobs,
    *,
    now: datetime | None = None,
) -> dict[str, object]:
    metrics = catalog_quality_metrics(jobs, now=now or FIXED_NOW)
    duplicate_rate = float(metrics["duplicate_rate"])
    assert duplicate_rate <= TARGET_DUPLICATE_RATE_MAX, (
        f"duplicate_rate {duplicate_rate} exceeds {TARGET_DUPLICATE_RATE_MAX}"
    )
    assert metrics["stale_closed_visible_count"] == 0, (
        "expected no stale closed jobs still visible, got "
        f"{metrics['stale_closed_visible_count']}"
    )
    return metrics


def _good_catalog_fixture_jobs() -> list[dict[str, object]]:
    jobs: list[dict[str, object]] = []
    for index in range(49):
        jobs.append(
            {
                "canonical_url": f"https://jobs.example.com/{index}",
                "url": f"https://jobs.example.com/{index}",
            }
        )
    jobs.append(
        {
            "canonical_url": "https://jobs.example.com/0",
            "url": "https://jobs.example.com/0?ref=dup",
        }
    )
    jobs.append(
        {
            "canonical_url": "https://jobs.example.com/recently-closed",
            "url": "https://jobs.example.com/recently-closed",
            "closed_at": "2026-06-29T08:00:00+00:00",
            "hidden": False,
        }
    )
    return jobs


def _high_duplicate_fixture_jobs() -> list[dict[str, object]]:
    return [
        {
            "canonical_url": "https://jobs.example.com/shared",
            "url": "https://jobs.example.com/shared",
        },
        {
            "canonical_url": "https://jobs.example.com/shared",
            "url": "https://jobs.example.com/shared?a=1",
        },
        {
            "canonical_url": "https://jobs.example.com/shared",
            "url": "https://jobs.example.com/shared?b=2",
        },
        {
            "canonical_url": "https://jobs.example.com/unique",
            "url": "https://jobs.example.com/unique",
        },
    ]


def _catalog_jobs_from_db(conn) -> list[dict[str, object]]:
    rows = conn.execute(
        """
        SELECT source_url, apply_url, external_id, status, last_seen_at
        FROM jobs
        ORDER BY id
        """
    ).fetchall()
    jobs: list[dict[str, object]] = []
    for row in rows:
        job: dict[str, object] = {
            "canonical_url": row["source_url"],
            "url": row["source_url"],
        }
        if row["status"] == "closed":
            job["closed_at"] = row["last_seen_at"]
        jobs.append(job)
    return jobs


def _write_refresh_seed(seed_path: Path) -> None:
    seed_path.write_text(
        json.dumps(
            [
                {
                    "name": "Example Greenhouse",
                    "aliases": [],
                    "tags": ["ai_infra"],
                    "stage": "growth",
                    "priority_tier": 1,
                    "careers_url": "https://boards.greenhouse.io/example",
                    "ats_type": "greenhouse",
                    "reviewed_at": "2026-05-08",
                },
                {
                    "name": "Example Lever",
                    "aliases": [],
                    "tags": ["ai_lab"],
                    "stage": "growth",
                    "priority_tier": 1,
                    "careers_url": "https://jobs.lever.co/example",
                    "ats_type": "lever",
                    "reviewed_at": "2026-05-08",
                },
            ]
        )
    )


def test_catalog_quality_gate_passes_for_good_fixture_jobs():
    metrics = assert_catalog_quality_gate(_good_catalog_fixture_jobs())

    assert metrics["job_count"] == 51
    assert metrics["duplicate_count"] == 1
    assert metrics["duplicate_rate"] <= TARGET_DUPLICATE_RATE_MAX
    assert metrics["target_duplicate_rate_max"] == TARGET_DUPLICATE_RATE_MAX
    assert metrics["stale_closed_visible_count"] == 0


def test_catalog_quality_gate_fails_on_high_duplicate_rate():
    with pytest.raises(AssertionError, match="duplicate_rate"):
        assert_catalog_quality_gate(_high_duplicate_fixture_jobs())


def test_fixture_refresh_db_rows_pass_catalog_quality_gate(tmp_path, capsys):
    db_path = tmp_path / "jobs.db"
    seed_path = tmp_path / "seed_companies.json"
    _write_refresh_seed(seed_path)

    exit_code = cli_main(
        [
            "refresh",
            "--db",
            str(db_path),
            "--seed",
            str(seed_path),
            "--fixture-dir",
            str(FIXTURES),
        ]
    )

    assert exit_code == 0
    capsys.readouterr()

    conn = connect(db_path)
    try:
        metrics = assert_catalog_quality_gate(_catalog_jobs_from_db(conn))
    finally:
        conn.close()

    assert metrics["job_count"] == 3
    assert metrics["duplicate_rate"] == 0.0
    assert metrics["duplicate_count"] == 0
