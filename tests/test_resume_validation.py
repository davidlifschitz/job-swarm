import pytest
from fastapi import UploadFile

from ml_job_swarm.resume_validation import validate_supported_resume_upload


def _upload(filename: str, content_type: str) -> UploadFile:
    return UploadFile(filename=filename, file=object(), headers={"content-type": content_type})


def test_accepts_pdf_by_suffix_only():
    validate_supported_resume_upload(_upload("resume.pdf", "application/octet-stream"))


def test_accepts_docx_by_content_type_only():
    validate_supported_resume_upload(
        _upload(
            "resume.bin",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    )


def test_rejects_unknown_upload():
    with pytest.raises(Exception) as exc:
        validate_supported_resume_upload(_upload("resume.txt", "text/plain"))
    assert exc.value.status_code == 400
