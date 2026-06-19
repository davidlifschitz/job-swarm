from __future__ import annotations

import re
import sqlite3
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


PARSER_NAME = "plain_text_sections"
PARSER_VERSION = "1"
LOW_CONFIDENCE_THRESHOLD = 0.6

SECTION_HEADINGS = {
    "summary": "summary",
    "professional summary": "summary",
    "profile": "summary",
    "skills": "skills",
    "technical skills": "skills",
    "experience": "experience",
    "work experience": "experience",
    "professional experience": "experience",
    "employment": "experience",
    "education": "education",
    "projects": "projects",
    "certifications": "certifications",
}

TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9+#.-]*")
SKILL_SPLIT_RE = re.compile(r"[,;|]")


class ResumeExtractionError(Exception):
    pass


@dataclass(frozen=True)
class ResumeParseResult:
    sections: dict[str, str]
    keywords: list[str]
    parser_name: str
    parser_confidence: float
    warnings: list[str]
    needs_vision_fallback: bool


def parse_resume_text(text: str) -> ResumeParseResult:
    cleaned_text = _normalize_text(text)
    sections = _parse_sections(cleaned_text)
    keywords = _extract_keywords(sections)
    confidence = _confidence(cleaned_text, sections)
    warnings: list[str] = []
    if confidence < LOW_CONFIDENCE_THRESHOLD:
        warnings.append("low_confidence_parse")

    return ResumeParseResult(
        sections=sections,
        keywords=keywords,
        parser_name=PARSER_NAME,
        parser_confidence=confidence,
        warnings=warnings,
        needs_vision_fallback=confidence < LOW_CONFIDENCE_THRESHOLD,
    )


def record_parse_run(
    conn: sqlite3.Connection,
    resume_asset_id: int,
    result: ResumeParseResult,
    consented_at: datetime | None,
) -> int:
    status = "needs_vision_fallback" if result.needs_vision_fallback else "parsed"
    if result.needs_vision_fallback:
        fallback_status = "consented" if consented_at else "pending_consent"
    else:
        fallback_status = "not_needed"
    fallback_consented_at = consented_at.isoformat() if consented_at else None

    cursor = conn.execute(
        """
        INSERT INTO resume_parse_runs (
          resume_asset_id,
          parser,
          parser_version,
          status,
          confidence,
          vision_fallback_status,
          vision_fallback_consented_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            resume_asset_id,
            result.parser_name,
            PARSER_VERSION,
            status,
            result.parser_confidence,
            fallback_status,
            fallback_consented_at,
        ),
    )
    parse_run_id = int(cursor.lastrowid)

    for sort_order, (section_type, section_text) in enumerate(result.sections.items()):
        conn.execute(
            """
            INSERT INTO resume_sections (
              parse_run_id,
              section_type,
              heading,
              text,
              sort_order
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (parse_run_id, section_type, section_type.title(), section_text, sort_order),
        )

    for keyword in result.keywords:
        conn.execute(
            """
            INSERT INTO resume_keywords (parse_run_id, keyword)
            VALUES (?, ?)
            """,
            (parse_run_id, keyword),
        )

    conn.commit()
    return parse_run_id


def extract_text_from_file(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".txt":
        return path.read_text()
    if suffix == ".pdf":
        return _extract_pdf_text(path)
    if suffix == ".docx":
        return _extract_docx_text(path)
    raise ResumeExtractionError(f"Unsupported resume file type: {suffix}")


def extract_text_from_bytes(content: bytes, filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temp_file:
        temp_file.write(content)
        temp_path = Path(temp_file.name)
    try:
        return extract_text_from_file(temp_path)
    finally:
        temp_path.unlink(missing_ok=True)


def _extract_pdf_text(path: Path) -> str:
    try:
        import fitz  # type: ignore[import-not-found]
    except ImportError as exc:
        raise ResumeExtractionError("PyMuPDF is required to parse PDF resumes") from exc

    text_parts: list[str] = []
    with fitz.open(path) as document:
        for page in document:
            text_parts.append(page.get_text())
    return "\n".join(text_parts)


def _extract_docx_text(path: Path) -> str:
    try:
        from docx import Document  # type: ignore[import-not-found]
    except ImportError as exc:
        raise ResumeExtractionError("python-docx is required to parse DOCX resumes") from exc

    document = Document(path)
    return "\n".join(paragraph.text for paragraph in document.paragraphs)


def _normalize_text(text: str) -> str:
    return "\n".join(line.strip() for line in text.splitlines()).strip()


def _parse_sections(text: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current_section: str | None = None

    for line in text.splitlines():
        if not line:
            continue
        heading = SECTION_HEADINGS.get(line.strip().casefold().rstrip(":"))
        if heading:
            current_section = heading
            sections.setdefault(current_section, [])
            continue
        if current_section is not None:
            sections[current_section].append(line)

    if not sections and text:
        sections["unclassified"] = [text]

    return {
        section: "\n".join(lines).strip()
        for section, lines in sections.items()
        if "\n".join(lines).strip()
    }


def _extract_keywords(sections: dict[str, str]) -> list[str]:
    candidates: list[str] = []
    skills_text = sections.get("skills", "")
    if skills_text:
        candidates.extend(
            part.strip().casefold()
            for part in SKILL_SPLIT_RE.split(skills_text)
            if part.strip()
        )

    all_text = " ".join(sections.values())
    common_terms = {
        "python",
        "pytorch",
        "sql",
        "kubernetes",
        "distributed systems",
        "machine learning",
        "retrieval",
        "ranking",
    }
    lower_text = all_text.casefold()
    candidates.extend(term for term in common_terms if term in lower_text)

    keywords: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        normalized = " ".join(candidate.split())
        if normalized and normalized not in seen:
            seen.add(normalized)
            keywords.append(normalized)
    return keywords[:30]


def _confidence(text: str, sections: dict[str, str]) -> float:
    section_count = len([value for value in sections.values() if value])
    token_count = len(TOKEN_RE.findall(text))
    if token_count < 12:
        return 0.2
    if section_count >= 4:
        return 0.95
    if section_count >= 2 and token_count >= 10:
        return 0.75
    if section_count == 1 and token_count >= 30:
        return 0.55
    return 0.35
