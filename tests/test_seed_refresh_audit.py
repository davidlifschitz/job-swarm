from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

from ml_job_swarm import cli
from ml_job_swarm.ingest import AdapterRegistry, RawJob, RefreshError
from ml_job_swarm.store import connect

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = REPO_ROOT / "tests" / "fixtures"
SCRIPT_PATH = REPO_ROOT / "scripts" / "seed_refresh_audit.py"


def _load_audit_module():
    spec = importlib.util.spec_from_file_location("seed_refresh_audit", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


audit = _load_audit_module()


class FailingAdapter:
    def __init__(self, error: RefreshError):
        self._error = error

    def fetch_jobs(self, source):
        raise self._error


def test_fixture_refresh_audit_passes_with_subset_seed(tmp_path, capsys):
    db_path = tmp_path / "jobs.db"
    seed_path = audit.write_fixture_seed_subset(tmp_path / "seed_companies.json")

    exit_code = audit.main(
        [
            "--db",
            str(db_path),
            "--seed",
            str(seed_path),
            "--fixture-dir",
            str(FIXTURES),
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert payload["audit_passed"] is True
    assert payload["audit_violations"] == []
    assert payload["refresh_summary"]["sources_attempted"] == 2
    assert payload["refresh_summary"]["sources_succeeded"] == 2
    assert payload["refresh_summary"]["jobs_seen"] == 3
    assert payload["source_failures"] == []
    assert payload["product_metrics"]["source_refresh"]["sources_attempted"] == 2
    assert payload["product_metrics"]["source_refresh"]["sources_succeeded"] == 2
    assert (
        payload["product_metrics"]["source_refresh"]["sources_have_visible_failure_reasons"]
        is True
    )

    conn = connect(db_path)
    assert conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 3


def test_fixture_refresh_audit_reports_visible_failure_reasons(tmp_path, capsys, monkeypatch):
    db_path = tmp_path / "jobs.db"
    seed_path = audit.write_fixture_seed_subset(tmp_path / "seed_companies.json")
    monkeypatch.setattr(
        cli,
        "_fixture_registry",
        lambda fixture_dir: AdapterRegistry(
            {
                "greenhouse": FailingAdapter(
                    RefreshError(
                        "blocked by source",
                        "blocked_response",
                        status_code=403,
                    )
                ),
                "lever": cli.FixtureAdapter(
                    [
                        RawJob(
                            external_id="lever-only",
                            title="Lever Fixture Job",
                            source_url="https://jobs.lever.co/example/lever-only",
                        )
                    ]
                ),
            }
        ),
    )

    exit_code = audit.main(
        [
            "--db",
            str(db_path),
            "--seed",
            str(seed_path),
            "--fixture-dir",
            str(FIXTURES),
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert payload["audit_passed"] is False
    assert "source_success_rate_below_target" in payload["audit_violations"]
    assert payload["refresh_summary"]["sources_attempted"] == 2
    assert payload["refresh_summary"]["sources_succeeded"] == 1
    assert payload["refresh_summary"]["failures"] == 1
    assert len(payload["source_failures"]) == 1
    assert payload["source_failures"][0]["event_type"] == "blocked_response"
    assert payload["source_failures"][0]["reason"] == "blocked by source"
    assert payload["source_failures"][0]["status_code"] == 403
    assert (
        payload["product_metrics"]["source_refresh"]["sources_have_visible_failure_reasons"]
        is True
    )
    assert payload["product_metrics"]["source_refresh"]["visible_failure_reason_count"] == 1


def test_fixture_refresh_audit_marks_missing_failure_reasons(tmp_path, monkeypatch):
    db_path = tmp_path / "jobs.db"
    seed_path = audit.write_fixture_seed_subset(tmp_path / "seed_companies.json")
    monkeypatch.setattr(
        cli,
        "_fixture_registry",
        lambda fixture_dir: AdapterRegistry(
            {
                "greenhouse": FailingAdapter(
                    RefreshError(
                        "blocked by source",
                        "blocked_response",
                        status_code=403,
                    )
                ),
                "lever": FailingAdapter(
                    RefreshError(
                        "rate limited",
                        "rate_limited",
                        status_code=429,
                    )
                ),
            }
        ),
    )
    monkeypatch.setattr(audit, "load_source_failures", lambda conn, since_run_id: [])

    payload, exit_code = audit.run_seed_refresh_audit(
        db_path=db_path,
        seed_path=seed_path,
        fixture_dir=FIXTURES,
    )
    assert exit_code == 1
    assert payload["audit_passed"] is False
    assert "missing_visible_failure_reasons" in payload["audit_violations"]
    assert payload["refresh_summary"]["sources_attempted"] == 2
    assert payload["refresh_summary"]["sources_succeeded"] == 0
    assert payload["source_failures"] == []
    assert (
        payload["product_metrics"]["source_refresh"]["sources_have_visible_failure_reasons"]
        is False
    )
    assert payload["product_metrics"]["source_refresh"]["missing_failure_reason_count"] == 2


def test_fixture_refresh_audit_script_runs_via_subprocess(tmp_path):
    db_path = tmp_path / "jobs.db"
    seed_path = audit.write_fixture_seed_subset(tmp_path / "seed_companies.json")

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
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

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["audit_passed"] is True
    assert payload["refresh_summary"]["sources_attempted"] == 2
    assert payload["refresh_summary"]["sources_succeeded"] == 2
