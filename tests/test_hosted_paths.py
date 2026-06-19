from ml_job_swarm.hosting import ensure_hosted_directories, hosted_paths_from_env, is_hosted_deployment


def test_hosted_paths_default_to_local_layout():
    paths = hosted_paths_from_env({})

    assert paths["data_dir"] == ""
    assert paths["db_path"] == "jobs.db"
    assert paths["resume_asset_dir"] == ".ml-job-swarm/resume-assets"


def test_hosted_paths_use_data_dir_for_db_and_resume_assets():
    paths = hosted_paths_from_env({"ML_JOB_SWARM_DATA_DIR": "/data"})

    assert paths["data_dir"] == "/data"
    assert paths["db_path"] == "/data/jobs.db"
    assert paths["resume_asset_dir"] == "/data/resume-assets"


def test_hosted_paths_honor_explicit_overrides():
    paths = hosted_paths_from_env(
        {
            "ML_JOB_SWARM_DATA_DIR": "/data",
            "ML_JOB_SWARM_DB_PATH": "/data/custom.db",
            "ML_JOB_SWARM_RESUME_ASSET_DIR": "/data/assets",
        }
    )

    assert paths["db_path"] == "/data/custom.db"
    assert paths["resume_asset_dir"] == "/data/assets"


def test_ensure_hosted_directories_creates_parents(tmp_path):
    paths = {
        "db_path": str(tmp_path / "nested" / "jobs.db"),
        "resume_asset_dir": str(tmp_path / "nested" / "resume-assets"),
    }

    ensure_hosted_directories(paths)

    assert paths["db_path"].startswith(str(tmp_path))
    assert (tmp_path / "nested" / "resume-assets").is_dir()


def test_is_hosted_deployment_detects_railway_domain():
    assert is_hosted_deployment({"RAILWAY_PUBLIC_DOMAIN": "ml-job-swarm.up.railway.app"}) is True
    assert is_hosted_deployment({}) is False