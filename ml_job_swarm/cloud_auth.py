from __future__ import annotations

import os

from fastapi import HTTPException, Request

from ml_job_swarm.supabase_auth import supabase_auth_enabled

SERVICE_TOKEN_HEADER = "x-cloud-service-token"


def cloud_service_token_from_env(env: dict[str, str] | None = None) -> str | None:
    source = env if env is not None else os.environ
    token = (source.get("ML_JOB_SWARM_CLOUD_SERVICE_TOKEN") or "").strip()
    return token or None


def is_cloud_service_request(request: Request) -> bool:
    configured = cloud_service_token_from_env()
    if not configured:
        return False
    provided = request.headers.get(SERVICE_TOKEN_HEADER, "").strip()
    return bool(provided) and provided == configured


def require_cloud_api_access(request: Request) -> None:
    if not supabase_auth_enabled():
        return
    if getattr(request.state, "user_id", None):
        return
    if is_cloud_service_request(request):
        request.state.cloud_service_auth = True
        return
    raise HTTPException(status_code=401, detail="unauthorized")
