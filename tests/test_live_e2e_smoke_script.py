import json
import subprocess
import zipfile

import scripts.live_e2e_smoke as live_e2e_smoke
from scripts.live_e2e_smoke import (
    DEFAULT_BOARD_URL,
    parse_refresh_summary,
    write_resume_docx,
    write_seed_catalog,
)


def test_write_seed_catalog_creates_single_public_greenhouse_source(tmp_path):
    seed_path = write_seed_catalog(tmp_path)

    payload = json.loads(seed_path.read_text())

    assert payload == [
        {
            "name": "Anthropic",
            "aliases": [],
            "tags": ["ai_lab"],
            "stage": "growth",
            "priority_tier": 1,
            "careers_url": DEFAULT_BOARD_URL,
            "ats_type": "greenhouse",
            "reviewed_at": "2026-05-11",
        }
    ]


def test_write_resume_docx_contains_parseable_resume_sections(tmp_path):
    resume_path = write_resume_docx(tmp_path)

    assert resume_path.suffix == ".docx"
    with zipfile.ZipFile(resume_path) as archive:
        document_xml = archive.read("word/document.xml").decode("utf-8")
    assert "Summary" in document_xml
    assert "Skills" in document_xml
    assert "Experience" in document_xml
    assert "Python" in document_xml


def test_parse_refresh_summary_extracts_numeric_counts():
    summary = parse_refresh_summary(
        "refresh_status=completed&jobs_seen=422&sources_attempted=1"
        "&sources_succeeded=1"
    )

    assert summary == {
        "jobs_seen": 422,
        "sources_attempted": 1,
        "sources_succeeded": 1,
    }


def test_start_server_routes_uvicorn_output_to_artifact_log(tmp_path, monkeypatch):
    captured = {}

    class FakeProcess:
        def poll(self):
            return 0

    def fake_popen(command, **kwargs):
        captured["command"] = command
        captured.update(kwargs)
        return FakeProcess()

    monkeypatch.setattr(live_e2e_smoke.subprocess, "Popen", fake_popen)
    log_path = tmp_path / "uvicorn.log"

    handle = live_e2e_smoke._start_server(
        host="127.0.0.1",
        port=43210,
        db_path=tmp_path / "browser.db",
        seed_path=tmp_path / "seed.json",
        log_path=log_path,
    )

    assert handle.log_path == log_path
    assert captured["stdout"].name == str(log_path)
    assert captured["stderr"] is subprocess.STDOUT
    assert captured["text"] is True
    assert "uvicorn" in captured["command"]
    assert captured["env"]["ML_JOB_SWARM_DB_PATH"] == str(tmp_path / "browser.db")

    live_e2e_smoke._stop_server(handle)

    assert captured["stdout"].closed


def test_main_prints_quantitative_product_metrics(tmp_path, monkeypatch, capsys):
    class FakeProcess:
        def poll(self):
            return 0

    def fake_start_server(**kwargs):
        log_path = tmp_path / "uvicorn.log"
        return live_e2e_smoke.ServerHandle(
            process=FakeProcess(),
            log_file=log_path.open("w"),
            log_path=log_path,
        )

    def fake_run_browser_smoke(**kwargs):
        return {
            "status": "browser_e2e_ok",
            "base_url": kwargs["base_url"],
            "jobs_seen": 422,
            "sources_attempted": 1,
            "sources_succeeded": 1,
            "dashboard_screenshot": str(tmp_path / "dashboard.png"),
            "saved_jobs_screenshot": str(tmp_path / "saved.png"),
            "prepared_screenshot": str(tmp_path / "prepared.png"),
        }

    monkeypatch.setattr(live_e2e_smoke, "_start_server", fake_start_server)
    monkeypatch.setattr(live_e2e_smoke, "_wait_for_app", lambda *args, **kwargs: None)
    monkeypatch.setattr(live_e2e_smoke, "run_browser_smoke", fake_run_browser_smoke)
    monkeypatch.setattr(
        live_e2e_smoke,
        "manual_submit_boundary_report",
        lambda root: {"external_submit_paths": ["unsafe.py"]},
        raising=False,
    )

    exit_code = live_e2e_smoke.main(["--artifact-dir", str(tmp_path)])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["product_metrics"]["first_run"]["browser_e2e_ok"] is True
    assert (
        payload["product_metrics"]["source_refresh"]["supported_source_success_rate"]
        == 1.0
    )
    assert payload["product_metrics"]["manual_submission"]["external_submit_paths"] == 1
