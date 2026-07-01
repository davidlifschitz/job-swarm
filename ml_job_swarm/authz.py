from __future__ import annotations

import os

from fastapi import HTTPException, Request

from ml_job_swarm.supabase_auth import supabase_auth_enabled


def admin_user_ids_from_env(env: dict[str, str] | None = None) -> set[str]:
    source = env if env is not None else os.environ
    raw = (source.get("ML_JOB_SWARM_ADMIN_USER_IDS") or "").strip()
    if not raw:
        return set()
    return {item.strip() for item in raw.split(",") if item.strip()}


def require_admin_access(request: Request) -> None:
    if not supabase_auth_enabled():
        return
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="unauthorized")
    allowed = admin_user_ids_from_env()
    if not allowed or user_id not in allowed:
        raise HTTPException(status_code=403, detail="admin access denied")
