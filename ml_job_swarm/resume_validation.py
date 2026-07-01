from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException, UploadFile

SUPPORTED_RESUME_TYPES = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
}


def validate_supported_resume_upload(resume: UploadFile) -> None:
    suffix = Path(resume.filename or "").suffix.casefold()
    allowed_suffixes = set(SUPPORTED_RESUME_TYPES.values())
    if suffix in allowed_suffixes:
        return
    content_type = (resume.content_type or "").split(";", 1)[0].strip().lower()
    if content_type in SUPPORTED_RESUME_TYPES:
        return
    raise HTTPException(status_code=400, detail="Resume must be a PDF or DOCX file")


def normalized_resume_content_type(resume: UploadFile) -> str:
    suffix = Path(resume.filename or "").suffix.casefold()
    for content_type, extension in SUPPORTED_RESUME_TYPES.items():
        if suffix == extension:
            return content_type
    content_type = (resume.content_type or "").split(";", 1)[0].strip().lower()
    if content_type in SUPPORTED_RESUME_TYPES:
        return content_type
    raise HTTPException(status_code=400, detail="Resume must be a PDF or DOCX file")
