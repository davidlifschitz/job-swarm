import importlib.metadata
import json
import subprocess
import sys
from pathlib import Path

import pytest

from ml_job_swarm import cli
from ml_job_swarm.cli import main
from ml_job_swarm.ingest import AdapterRegistry, RawJob, RefreshError
from ml_job_swarm.store import connect


FIXTURES = Path(__file__).parent / "fixtures"


class FailingAdapter:
    def __init__(self, error: RefreshError):
        self._error = error

    def fetch_jobs(self, source):
        raise self._error


def test_refresh_command_imports_seed_and_runs_fixture_adapters(tmp_path, capsys):
    db_path = tmp_path / "jobs.db"
    seed_path = tmp_path / "seed_companies.json"
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
                {
                    "name": "Example Custom",
                    "aliases": [],
                    "tags": ["developer_tools"],
                    "stage": "growth",
                    "priority_tier": 1,
                    "careers_url": "https://example.com/careers",
                    "ats_type": "custom",
                    "reviewed_at": "2026-05-08",
                },
            ]
        )
    )

    exit_code = main(
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
    summary = json.loads(capsys.readouterr().out)
    assert summary == {
        "blocked": 0,
        "failures": 0,
        "friction_events": {},
        "friction_status_codes": {},
        "imported_companies": 3,
        "jobs_closed": 0,
        "jobs_seen": 3,
        "suspicious_empty": 0,
        "sources_attempted": 2,
        "sources_refreshed": 2,
        "sources_seen": 2,
        "sources_succeeded": 2,
        "sources_skipped": 1,
    }
    conn = connect(db_path)
    assert conn.execute("SELECT COUNT(*) FROM companies").fetchone()[0] == 3
    assert conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 3
    assert conn.execute("SELECT COUNT(*) FROM job_snapshots").fetchone()[0] == 3


def test_refresh_command_can_use_public_ats_registry(tmp_path, capsys, monkeypatch):
    db_path = tmp_path / "jobs.db"
    seed_path = tmp_path / "seed_companies.json"
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
                    "name": "Example Custom",
                    "aliases": [],
                    "tags": ["developer_tools"],
                    "stage": "growth",
                    "priority_tier": 1,
                    "careers_url": "https://example.com/careers",
                    "ats_type": "custom",
                    "reviewed_at": "2026-05-08",
                },
            ]
        )
    )
    monkeypatch.setattr(
        cli,
        "public_ats_registry",
        lambda: AdapterRegistry(
            {
                "greenhouse": cli.FixtureAdapter(
                    [
                        RawJob(
                            external_id="realish-1",
                            title="Public ATS ML Engineer",
                            source_url="https://boards.greenhouse.io/example/jobs/1",
                        )
                    ]
                )
            }
        ),
    )

    exit_code = main(
        [
            "refresh",
            "--public-ats",
            "--db",
            str(db_path),
            "--seed",
            str(seed_path),
        ]
    )

    assert exit_code == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary == {
        "blocked": 0,
        "failures": 0,
        "friction_events": {},
        "friction_status_codes": {},
        "imported_companies": 2,
        "jobs_closed": 0,
        "jobs_seen": 1,
        "suspicious_empty": 0,
        "sources_attempted": 1,
        "sources_refreshed": 1,
        "sources_seen": 1,
        "sources_succeeded": 1,
        "sources_skipped": 1,
    }
    conn = connect(db_path)
    assert conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 1
    assert conn.execute("SELECT title FROM jobs").fetchone()[0] == (
        "Public ATS ML Engineer"
    )


def test_refresh_command_reports_suspicious_empty_sources(
    tmp_path, capsys, monkeypatch
):
    db_path = tmp_path / "jobs.db"
    seed_path = tmp_path / "seed_companies.json"
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
                }
            ]
        )
    )
    monkeypatch.setattr(
        cli,
        "public_ats_registry",
        lambda: AdapterRegistry({"greenhouse": cli.FixtureAdapter([])}),
    )

    exit_code = main(
        [
            "refresh",
            "--public-ats",
            "--db",
            str(db_path),
            "--seed",
            str(seed_path),
        ]
    )

    assert exit_code == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["failures"] == 0
    assert summary["friction_events"] == {"empty_suspicious": 1}
    assert summary["friction_status_codes"] == {}
    assert summary["suspicious_empty"] == 1
    assert summary["jobs_seen"] == 0


def test_refresh_command_reports_friction_event_and_status_summaries(
    tmp_path, capsys, monkeypatch
):
    db_path = tmp_path / "jobs.db"
    seed_path = tmp_path / "seed_companies.json"
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
                }
            ]
        )
    )
    monkeypatch.setattr(
        cli,
        "public_ats_registry",
        lambda: AdapterRegistry(
            {
                "greenhouse": FailingAdapter(
                    RefreshError(
                        "blocked by source",
                        "blocked_response",
                        status_code=403,
                    )
                )
            }
        ),
    )

    exit_code = main(
        [
            "refresh",
            "--public-ats",
            "--db",
            str(db_path),
            "--seed",
            str(seed_path),
        ]
    )

    summary = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert summary["failures"] == 1
    assert summary["friction_events"] == {"blocked_response": 1}
    assert summary["friction_status_codes"] == {"403": 1}


def test_refresh_command_requires_adapter_mode(tmp_path, capsys):
    db_path = tmp_path / "jobs.db"

    with pytest.raises(SystemExit) as exc_info:
        main(["refresh", "--db", str(db_path)])

    assert exc_info.value.code == 2
    captured = capsys.readouterr()
    assert "--public-ats" in captured.err
    assert "--fixture-dir" in captured.err


def test_console_script_is_packaged():
    scripts = {
        entry_point.name: entry_point.value
        for entry_point in importlib.metadata.entry_points(group="console_scripts")
    }

    assert scripts["ml-job-swarm"] == "ml_job_swarm.cli:main"


def test_cli_module_execution_runs_refresh_command(tmp_path):
    db_path = tmp_path / "jobs.db"
    seed_path = tmp_path / "seed_companies.json"
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
                }
            ]
        )
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "ml_job_swarm.cli",
            "refresh",
            "--db",
            str(db_path),
            "--seed",
            str(seed_path),
            "--fixture-dir",
            str(FIXTURES),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    summary = json.loads(result.stdout)
    assert summary["jobs_seen"] == 2
    assert summary["sources_refreshed"] == 1
