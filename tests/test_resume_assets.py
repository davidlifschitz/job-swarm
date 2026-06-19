import base64

import pytest

import ml_job_swarm.resume_assets as resume_assets
from ml_job_swarm.resume_assets import (
    ResumeAssetStorageError,
    load_resume_asset_bytes,
    pdf_page_image_content_parts,
    persist_resume_asset,
)


def test_persist_resume_asset_writes_under_configured_dir(tmp_path):
    uri = persist_resume_asset(
        b"%PDF private resume bytes",
        original_filename="resume.pdf",
        digest="abc123",
        asset_dir=tmp_path,
    )

    assert uri == "local://resume-assets/abc123.pdf"
    assert load_resume_asset_bytes(uri, tmp_path) == b"%PDF private resume bytes"


def test_load_resume_asset_rejects_traversal(tmp_path):
    with pytest.raises(ResumeAssetStorageError):
        load_resume_asset_bytes("local://resume-assets/../secret.pdf", tmp_path)


def test_load_resume_asset_reports_missing_file(tmp_path):
    with pytest.raises(ResumeAssetStorageError):
        load_resume_asset_bytes("local://resume-assets/missing.pdf", tmp_path)


def test_pdf_page_image_content_parts_use_png_data_uris(monkeypatch):
    monkeypatch.setattr(
        resume_assets,
        "_render_pdf_pages_as_png",
        lambda content, max_pages: [b"page-one-png", b"page-two-png"],
    )

    parts = pdf_page_image_content_parts(b"%PDF private bytes", max_pages=2)

    assert len(parts) == 2
    assert parts[0]["type"] == "image_url"
    assert parts[0]["image_url"]["url"] == (
        "data:image/png;base64," + base64.b64encode(b"page-one-png").decode("ascii")
    )
