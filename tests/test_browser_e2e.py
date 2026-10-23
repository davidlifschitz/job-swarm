"""Real browser/app workflow with deterministic bytes at the ATS HTTP boundary."""
import threading

import pytest
import uvicorn

from ml_job_swarm.app import create_app
from ml_job_swarm.catalog import import_seed_companies
from scripts.live_e2e_smoke import (
    _free_port,
    _wait_for_app,
    run_browser_smoke,
    write_resume_docx,
    write_seed_catalog,
)


def test_browser_refresh_save_and_prepare_large_greenhouse_board(
    tmp_path, greenhouse_bulk_response,
):
    pytest.importorskip("playwright.sync_api", reason="Run with uv run --with playwright pytest")
    app = create_app(tmp_path / "browser.db")
    app.state.resume_asset_dir = tmp_path / "resumes"
    import_seed_companies(
        app.state.conn,
        write_seed_catalog(
            tmp_path, company_name="Example",
            board_url="https://boards.greenhouse.io/example",
        ),
    )
    port = _free_port("127.0.0.1")
    base_url = f"http://127.0.0.1:{port}"
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    try:
        _wait_for_app(base_url, timeout_seconds=30)
        summary = run_browser_smoke(
            base_url=base_url, resume_path=write_resume_docx(tmp_path),
            artifact_dir=tmp_path, browser_timeout_ms=60_000,
        )
        assert summary["status"] == "browser_e2e_ok"
        assert summary["sources_attempted"] == 1
        assert summary["sources_succeeded"] == 1
        assert summary["jobs_seen"] == 400
        assert app.state.conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 400
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        assert not thread.is_alive(), "Browser test server did not stop"
        app.state.conn.close()
