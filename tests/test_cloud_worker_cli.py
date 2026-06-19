from ml_job_swarm.cloud_worker import main


def test_cloud_worker_cli_runs_once_against_configured_database(tmp_path, capsys):
    db_path = tmp_path / "cloud-worker-cli.db"

    exit_code = main(
        [
            "--db-path",
            str(db_path),
            "--max-runs",
            "1",
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert '"runs_processed": 0' in output
    assert '"idle": true' in output
