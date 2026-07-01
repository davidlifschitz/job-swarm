from __future__ import annotations

from fastapi import HTTPException, UploadFile

MAX_RESUME_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_CSV_UPLOAD_BYTES = 5 * 1024 * 1024


async def read_upload_with_limit(upload: UploadFile, *, max_bytes: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await upload.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(status_code=413, detail="upload too large")
        chunks.append(chunk)
    return b"".join(chunks)
