from __future__ import annotations

import os
from pathlib import Path


def hosted_paths_from_env(env: dict[str, str] | None = None) -> dict[str, str]:
    source = env if env is not None else os.environ
    data_dir = (source.get("ML_JOB_SWARM_DATA_DIR") or "").strip()
    if not data_dir:
        db_path = (source.get("ML_JOB_SWARM_DB_PATH") or "jobs.db").strip()
        resume_asset_dir = (
            source.get("ML_JOB_SWARM_RESUME_ASSET_DIR") or ".ml-job-swarm/resume-assets"
        ).strip()
        return {
            "data_dir": "",
            "db_path": db_path,
            "resume_asset_dir": resume_asset_dir,
        }

    root = Path(data_dir).expanduser()
    db_path = (source.get("ML_JOB_SWARM_DB_PATH") or str(root / "jobs.db")).strip()
    resume_asset_dir = (
        source.get("ML_JOB_SWARM_RESUME_ASSET_DIR") or str(root / "resume-assets")
    ).strip()
    return {
        "data_dir": str(root),
        "db_path": db_path,
        "resume_asset_dir": resume_asset_dir,
    }


def ensure_hosted_directories(paths: dict[str, str]) -> None:
    Path(paths["db_path"]).parent.mkdir(parents=True, exist_ok=True)
    Path(paths["resume_asset_dir"]).mkdir(parents=True, exist_ok=True)


def is_hosted_deployment(env: dict[str, str] | None = None) -> bool:
    source = env if env is not None else os.environ
    if (source.get("ML_JOB_SWARM_DATA_DIR") or "").strip():
        return True
    for key in (
        "ML_JOB_SWARM_PUBLIC_URL",
        "PUBLIC_URL",
        "RENDER_EXTERNAL_URL",
        "VERCEL_URL",
        "RAILWAY_PUBLIC_DOMAIN",
        "FLY_APP_NAME",
    ):
        if (source.get(key) or "").strip():
            return True
    return False