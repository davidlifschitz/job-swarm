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
) -> str:
    root = _asset_root(asset_dir)
    root.mkdir(parents=True, exist_ok=True)
    suffix = _safe_suffix(original_filename)
    filename = f"{digest}{suffix}"
    path = _resolve_asset_name(filename, root)
    if not path.exists():
        path.write_bytes(content)
    return f"{RESUME_ASSET_URI_PREFIX}{filename}"


def load_resume_asset_bytes(
    storage_uri: str,
    asset_dir: str | Path | None = None,
) -> bytes:
    path = resolve_resume_asset_path(storage_uri, asset_dir)
    if not path.exists():
        raise ResumeAssetStorageError("Stored resume asset is unavailable")
    try:
        return path.read_bytes()
    except OSError as exc:
        raise ResumeAssetStorageError("Stored resume asset is unreadable") from exc


def resolve_resume_asset_path(
    storage_uri: str,
    asset_dir: str | Path | None = None,
) -> Path:
    if not storage_uri.startswith(RESUME_ASSET_URI_PREFIX):
        raise ResumeAssetStorageError("Unsupported resume asset storage URI")
    asset_name = storage_uri.removeprefix(RESUME_ASSET_URI_PREFIX)
    root = _asset_root(asset_dir)
    return _resolve_asset_name(asset_name, root)


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


def _asset_root(asset_dir: str | Path | None) -> Path:
    return Path(asset_dir) if asset_dir is not None else default_resume_asset_dir()


def _resolve_asset_name(asset_name: str, root: Path) -> Path:
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
