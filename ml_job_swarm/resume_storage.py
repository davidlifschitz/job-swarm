from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Protocol
from urllib.parse import quote

from ml_job_swarm.resume_assets import (
    RESUME_ASSET_URI_PREFIX,
    ResumeAssetStorageError,
    SUPPORTED_ASSET_SUFFIXES,
    default_resume_asset_dir,
)


SUPABASE_RESUME_URI_PREFIX = "supabase://resume-assets/"
DEFAULT_RESUME_STORAGE_BUCKET = "resume-assets"
_STORAGE_TIMEOUT_SECONDS = 30.0
_USER_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")


class ResumeStorageBackend(Protocol):
    def persist(
        self,
        content: bytes,
        *,
        original_filename: str,
        digest: str,
        user_id: str | None = None,
    ) -> str: ...

    def load_bytes(self, storage_uri: str) -> bytes: ...


class LocalResumeStorage:
    def __init__(self, *, asset_dir: str | Path | None = None) -> None:
        self._asset_dir = asset_dir

    def persist(
        self,
        content: bytes,
        *,
        original_filename: str,
        digest: str,
        user_id: str | None = None,
    ) -> str:
        del user_id
        root = _local_asset_root(self._asset_dir)
        root.mkdir(parents=True, exist_ok=True)
        suffix = _safe_suffix(original_filename)
        filename = f"{digest}{suffix}"
        path = _resolve_local_asset_name(filename, root)
        if not path.exists():
            path.write_bytes(content)
        return f"{RESUME_ASSET_URI_PREFIX}{filename}"

    def load_bytes(self, storage_uri: str) -> bytes:
        path = _resolve_local_storage_uri(storage_uri, asset_dir=self._asset_dir)
        if not path.exists():
            raise ResumeAssetStorageError("Stored resume asset is unavailable")
        try:
            return path.read_bytes()
        except OSError as exc:
            raise ResumeAssetStorageError("Stored resume asset is unreadable") from exc


class SupabaseResumeStorage:
    def __init__(
        self,
        *,
        supabase_url: str,
        service_role_key: str,
        bucket: str = DEFAULT_RESUME_STORAGE_BUCKET,
    ) -> None:
        self._supabase_url = supabase_url.rstrip("/")
        self._service_role_key = service_role_key
        self._bucket = bucket

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> SupabaseResumeStorage:
        source = env if env is not None else os.environ
        supabase_url = (source.get("SUPABASE_URL") or "").strip()
        service_role_key = (
            (source.get("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
            or (source.get("SUPABASE_SECRET_KEY") or "").strip()
        )
        bucket = (
            source.get("ML_JOB_SWARM_RESUME_STORAGE_BUCKET")
            or DEFAULT_RESUME_STORAGE_BUCKET
        ).strip()
        if not supabase_url or not service_role_key:
            raise ResumeAssetStorageError("Supabase resume storage is not configured")
        return cls(
            supabase_url=supabase_url,
            service_role_key=service_role_key,
            bucket=bucket,
        )

    def persist(
        self,
        content: bytes,
        *,
        original_filename: str,
        digest: str,
        user_id: str | None = None,
    ) -> str:
        object_path = _supabase_object_path(
            user_id=user_id,
            digest=digest,
            original_filename=original_filename,
        )
        try:
            import httpx
        except ImportError as exc:
            raise ResumeAssetStorageError(
                "httpx is required for Supabase resume storage. "
                "Install with: uv sync --extra hosted"
            ) from exc
        response = httpx.post(
            self._object_url(object_path),
            content=content,
            headers={
                "Authorization": f"Bearer {self._service_role_key}",
                "Content-Type": _content_type_for_filename(original_filename),
                "x-upsert": "true",
            },
            timeout=_STORAGE_TIMEOUT_SECONDS,
        )
        try:
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ResumeAssetStorageError("Supabase resume upload failed") from exc
        return f"{SUPABASE_RESUME_URI_PREFIX}{object_path}"

    def load_bytes(self, storage_uri: str) -> bytes:
        object_path = _parse_supabase_storage_uri(storage_uri)
        try:
            import httpx
        except ImportError as exc:
            raise ResumeAssetStorageError(
                "httpx is required for Supabase resume storage. "
                "Install with: uv sync --extra hosted"
            ) from exc
        response = httpx.get(
            self._object_url(object_path),
            headers={"Authorization": f"Bearer {self._service_role_key}"},
            timeout=_STORAGE_TIMEOUT_SECONDS,
        )
        try:
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ResumeAssetStorageError("Stored resume asset is unavailable") from exc
        return bytes(response.content)

    def _object_url(self, object_path: str) -> str:
        encoded = "/".join(quote(part, safe="") for part in object_path.split("/"))
        return (
            f"{self._supabase_url}/storage/v1/object/"
            f"{quote(self._bucket, safe='')}/{encoded}"
        )


def resume_storage_from_env(
    env: dict[str, str] | None = None,
    *,
    asset_dir: str | Path | None = None,
) -> ResumeStorageBackend:
    source = env if env is not None else os.environ
    if _supabase_storage_enabled(source):
        return SupabaseResumeStorage.from_env(source)
    return LocalResumeStorage(asset_dir=asset_dir)


def backend_for_storage_uri(
    storage_uri: str,
    *,
    asset_dir: str | Path | None = None,
    env: dict[str, str] | None = None,
) -> ResumeStorageBackend:
    if storage_uri.startswith(SUPABASE_RESUME_URI_PREFIX):
        return SupabaseResumeStorage.from_env(env)
    if storage_uri.startswith(RESUME_ASSET_URI_PREFIX):
        return LocalResumeStorage(asset_dir=asset_dir)
    raise ResumeAssetStorageError("Unsupported resume asset storage URI")


def _supabase_storage_enabled(env: dict[str, str]) -> bool:
    supabase_url = (env.get("SUPABASE_URL") or "").strip()
    service_role_key = (
        (env.get("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
        or (env.get("SUPABASE_SECRET_KEY") or "").strip()
    )
    return bool(supabase_url and service_role_key)


def _supabase_object_path(
    *,
    user_id: str | None,
    digest: str,
    original_filename: str,
) -> str:
    scoped_user_id = _storage_user_id(user_id)
    suffix = _safe_suffix(original_filename)
    return f"{scoped_user_id}/{digest}{suffix}"


def _parse_supabase_storage_uri(storage_uri: str) -> str:
    if not storage_uri.startswith(SUPABASE_RESUME_URI_PREFIX):
        raise ResumeAssetStorageError("Unsupported resume asset storage URI")
    object_path = storage_uri.removeprefix(SUPABASE_RESUME_URI_PREFIX)
    if not object_path or ".." in object_path.split("/"):
        raise ResumeAssetStorageError("Invalid resume asset storage URI")
    return object_path


def _storage_user_id(user_id: str | None) -> str:
    scoped = (user_id or "").strip() or "anonymous"
    if not _USER_ID_PATTERN.fullmatch(scoped):
        raise ResumeAssetStorageError("Invalid resume asset owner id")
    return scoped


def _content_type_for_filename(filename: str) -> str:
    suffix = Path(filename or "").suffix.lower()
    if suffix == ".pdf":
        return "application/pdf"
    if suffix == ".docx":
        return (
            "application/vnd.openxmlformats-officedocument."
            "wordprocessingml.document"
        )
    return "application/octet-stream"


def _local_asset_root(asset_dir: str | Path | None) -> Path:
    return Path(asset_dir) if asset_dir is not None else default_resume_asset_dir()


def _resolve_local_storage_uri(
    storage_uri: str,
    *,
    asset_dir: str | Path | None,
) -> Path:
    if not storage_uri.startswith(RESUME_ASSET_URI_PREFIX):
        raise ResumeAssetStorageError("Unsupported resume asset storage URI")
    asset_name = storage_uri.removeprefix(RESUME_ASSET_URI_PREFIX)
    root = _local_asset_root(asset_dir)
    return _resolve_local_asset_name(asset_name, root)


def _resolve_local_asset_name(asset_name: str, root: Path) -> Path:
    if not asset_name or Path(asset_name).name != asset_name:
        raise ResumeAssetStorageError("Invalid resume asset storage URI")
    path = (root / asset_name).resolve()
    root_resolved = root.resolve()
    if path.parent != root_resolved:
        raise ResumeAssetStorageError("Invalid resume asset storage URI")
    return path


def _safe_suffix(filename: str) -> str:
    suffix = Path(filename or "").suffix.lower()
    if suffix not in SUPPORTED_ASSET_SUFFIXES:
        return ""
    return suffix