from __future__ import annotations

import base64
import os
from pathlib import Path
from typing import Any


RESUME_ASSET_URI_PREFIX = "local://resume-assets/"
DEFAULT_RESUME_ASSET_DIR = Path(".ml-job-swarm") / "resume-assets"
SUPPORTED_ASSET_SUFFIXES = {".pdf", ".docx"}


class ResumeAssetStorageError(RuntimeError):
    pass


def default_resume_asset_dir() -> Path:
    configured = os.environ.get("ML_JOB_SWARM_RESUME_ASSET_DIR")
    if configured:
        return Path(configured).expanduser()
    return DEFAULT_RESUME_ASSET_DIR


def persist_resume_asset(
    content: bytes,
    *,
    original_filename: str,
    digest: str,
    asset_dir: str | Path | None = None,
    user_id: str | None = None,
) -> str:
    from ml_job_swarm.resume_storage import resume_storage_from_env

    backend = resume_storage_from_env(asset_dir=asset_dir)
    return backend.persist(
        content,
        original_filename=original_filename,
        digest=digest,
        user_id=user_id,
    )


def load_resume_asset_bytes(
    storage_uri: str,
    asset_dir: str | Path | None = None,
) -> bytes:
    from ml_job_swarm.resume_storage import backend_for_storage_uri

    backend = backend_for_storage_uri(storage_uri, asset_dir=asset_dir)
    return backend.load_bytes(storage_uri)


def resolve_resume_asset_path(
    storage_uri: str,
    asset_dir: str | Path | None = None,
) -> Path:
    from ml_job_swarm.resume_storage import _resolve_local_storage_uri

    return _resolve_local_storage_uri(storage_uri, asset_dir=asset_dir)


def pdf_page_image_content_parts(
    content: bytes,
    *,
    max_pages: int = 3,
) -> tuple[dict[str, Any], ...]:
    png_pages = _render_pdf_pages_as_png(content, max_pages=max_pages)
    if not png_pages:
        raise ResumeAssetStorageError("Stored resume PDF did not render pages")
    return tuple(
        {
            "type": "image_url",
            "image_url": {
                "url": "data:image/png;base64,"
                + base64.b64encode(page).decode("ascii"),
                "detail": "high",
            },
        }
        for page in png_pages
    )


def _render_pdf_pages_as_png(content: bytes, *, max_pages: int) -> list[bytes]:
    if max_pages < 1:
        raise ResumeAssetStorageError("max_pages must be at least 1")
    try:
        import fitz  # type: ignore[import-not-found]
    except ImportError as exc:
        raise ResumeAssetStorageError("PyMuPDF is required for PDF vision fallback") from exc

    pages: list[bytes] = []
    try:
        with fitz.open(stream=content, filetype="pdf") as document:
            for page_index in range(min(max_pages, len(document))):
                page = document[page_index]
                pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                pages.append(pixmap.tobytes("png"))
    except Exception as exc:
        raise ResumeAssetStorageError("Stored resume PDF could not be rendered") from exc
    return pages



