from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

from ml_job_swarm import cli
from ml_job_swarm.ingest import AdapterRegistry, RawJob, RefreshError
from ml_job_swarm.store import connect, init_db

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
    assert "refresh_failures" in payload["audit_violations"]
    assert any(
        "success rate" in violation.casefold()
        for violation in payload["audit_violations"]
    )
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
    assert "refresh_failures" in payload["audit_violations"]
    assert any(
        "visible failure reason" in violation.casefold()
        for violation in payload["audit_violations"]
    )
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


def _seed_live_evaluate_db(db_path: Path) -> tuple[int, dict[str, object]]:
    conn = connect(db_path)
    init_db(conn)
    conn.execute(
        "INSERT INTO ingestion_runs (status, source_count) VALUES ('succeeded', 0)"
    )
    previous_run_id = int(
        conn.execute("SELECT COALESCE(MAX(id), 0) FROM ingestion_runs").fetchone()[0]
    )
    conn.execute(
        "INSERT INTO ingestion_runs (status, source_count) VALUES ('failed', 10)"
    )
    new_run_id = int(
        conn.execute("SELECT COALESCE(MAX(id), 0) FROM ingestion_runs").fetchone()[0]
    )
    conn.execute(
        """
        INSERT INTO source_friction_events (
          ingestion_run_id,
          event_type,
          url,
          status_code,
          details_json
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            new_run_id,
            "blocked_response",
            "https://boards.greenhouse.io/example",
            403,
            json.dumps({"reason": "blocked by source"}),
        ),
    )
    conn.commit()
    conn.close()

    refresh_summary = {
        "sources_attempted": 10,
        "sources_succeeded": 9,
        "jobs_seen": 50,
        "failures": 0,
    }
    return previous_run_id, refresh_summary


def test_evaluate_live_refresh_audit_loads_friction_events(tmp_path):
    db_path = tmp_path / "audit.db"
    previous_run_id, refresh_summary = _seed_live_evaluate_db(db_path)
    refresh_summary_path = tmp_path / "refresh_summary.json"
    refresh_summary_path.write_text(json.dumps(refresh_summary), encoding="utf-8")
    output_path = tmp_path / "nightly_seed_audit.json"

    payload, exit_code = audit.evaluate_live_refresh_audit(
        db_path=db_path,
        refresh_summary_path=refresh_summary_path,
        previous_run_id=previous_run_id,
        output_path=output_path,
    )

    assert exit_code == 0
    assert payload["audit_passed"] is True
    assert payload["audit_violations"] == []
    assert len(payload["source_failures"]) == 1
    assert payload["source_failures"][0]["event_type"] == "blocked_response"
    assert payload["source_failures"][0]["reason"] == "blocked by source"
    assert payload["source_failures"][0]["status_code"] == 403
    assert (
        payload["product_metrics"]["source_refresh"]["sources_have_visible_failure_reasons"]
        is True
    )
    assert output_path.is_file()
    written = json.loads(output_path.read_text(encoding="utf-8"))
    assert written["audit_passed"] is True
    assert written["source_failures"] == payload["source_failures"]


def test_evaluate_live_refresh_audit_cli_mode(tmp_path, capsys):
    db_path = tmp_path / "audit.db"
    previous_run_id, refresh_summary = _seed_live_evaluate_db(db_path)
    refresh_summary_path = tmp_path / "refresh_summary.json"
    refresh_summary_path.write_text(json.dumps(refresh_summary), encoding="utf-8")
    output_path = tmp_path / "nightly_seed_audit.json"

    exit_code = audit.main(
        [
            "--evaluate-live",
            "--db",
            str(db_path),
            "--refresh-summary",
            str(refresh_summary_path),
            "--previous-run-id",
            str(previous_run_id),
            "--output",
            str(output_path),
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert payload["audit_passed"] is True
    assert len(payload["source_failures"]) == 1
    assert output_path.is_file()
