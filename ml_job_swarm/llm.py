from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, TypeVar

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator


REQUIRED_QUESTION_IDS = ["role", "level", "location", "work_mode", "company_stage"]
FIT_LABELS = {"Strong fit", "Possible fit", "Mismatch risk", "Filtered out"}
PRIVATE_ECHO_KEYS = {
    "prompt",
    "raw_prompt",
    "private_prompt",
    "resume_text",
    "raw_resume_text",
    "messages",
    "request_body",
}
PRIVATE_RESPONSE_KEYS = PRIVATE_ECHO_KEYS | {"extracted_text"}

ResponseModel = TypeVar("ResponseModel", bound=BaseModel)


class ProfileDraftResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    headline: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    keywords: list[str] = Field(min_length=1)
    seniority_signals: list[str] = Field(default_factory=list)


class QuestionnaireQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: Literal["role", "level", "location", "work_mode", "company_stage"]
    prompt: str = Field(min_length=1)
    options: list[str] = Field(min_length=1)


class QuestionnaireResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    questions: list[QuestionnaireQuestion]

    @model_validator(mode="after")
    def require_fixed_question_ids(self) -> "QuestionnaireResponse":
        ids = [question.id for question in self.questions]
        if ids != REQUIRED_QUESTION_IDS:
            raise ValueError(f"Question ids must be exactly {REQUIRED_QUESTION_IDS}")
        return self


class ResumeRewriteResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    section_id: int
    replacement_text: str = Field(min_length=1)
    rationale: str = Field(min_length=1)
    risk_flags: list[str] = Field(default_factory=list)


class FitGateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fit_score: int = Field(ge=0, le=100)
    label: str
    reasons: list[str] = Field(min_length=1)
    risks: list[str]
    recommendation: str = Field(min_length=1)

    @field_validator("label")
    @classmethod
    def validate_label(cls, label: str) -> str:
        if label not in FIT_LABELS:
            raise ValueError(f"label must be one of {sorted(FIT_LABELS)}")
        return label


class VisionFallbackResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    extracted_text: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    warnings: list[str] = Field(default_factory=list)


@dataclass(frozen=True)
class LLMRequest:
    feature: str
    schema_version: str
    model: str
    input_reference: str
    private_prompt: str
    provider: str = "openrouter"
    private_content_parts: tuple[dict[str, Any], ...] = field(default_factory=tuple)


class LLMProvider(Protocol):
    def complete(self, request: LLMRequest) -> dict[str, Any]: ...


@dataclass(frozen=True)
class FitGatePayload:
    job: dict[str, Any]
    company: dict[str, Any]
    target_profile: dict[str, Any]
    rules_result: dict[str, Any]


class FitGateClient(Protocol):
    provider: str
    model: str
    schema_version: str

    def review_fit(self, payload: FitGatePayload) -> FitGateResponse | dict[str, Any]: ...


def request_structured_response(
    conn: sqlite3.Connection,
    provider: LLMProvider,
    request: LLMRequest,
    response_model: type[ResponseModel],
) -> ResponseModel:
    last_payload: dict[str, Any] | None = None
    last_error: ValidationError | None = None

    for _attempt in range(2):
        payload = provider.complete(request)
        last_payload = payload
        validation_payload = _validation_payload(payload)
        try:
            parsed = response_model.model_validate(validation_payload)
        except ValidationError as exc:
            last_error = exc
            continue

        record_llm_request(
            conn,
            request,
            status="succeeded",
            response_payload=validation_payload,
        )
        return parsed

    assert last_error is not None
    record_llm_request(
        conn,
        request,
        status="failed",
        response_payload=_safe_response_payload(last_payload or {}),
        error=str(last_error),
    )
    raise last_error


def record_llm_request(
    conn: sqlite3.Connection,
    request: LLMRequest,
    *,
    status: str,
    response_payload: dict[str, Any],
    error: str | None = None,
) -> int:
    cursor = conn.execute(
        """
        INSERT INTO llm_requests (
          provider,
          model,
          feature,
          schema_version,
          status,
          request_hash,
          response_json,
          error
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            request.provider,
            request.model,
            request.feature,
            request.schema_version,
            status,
            _request_hash(request),
            json.dumps(
                {
                    "input_reference": request.input_reference,
                    "payload": _safe_response_payload(response_payload),
                },
                sort_keys=True,
            ),
            error,
        ),
    )
    conn.commit()
    return int(cursor.lastrowid)


def _request_hash(request: LLMRequest) -> str:
    payload = {
        "provider": request.provider,
        "model": request.model,
        "feature": request.feature,
        "schema_version": request.schema_version,
        "input_reference": request.input_reference,
        "private_prompt_sha256": hashlib.sha256(
            request.private_prompt.encode("utf-8")
        ).hexdigest(),
        "private_content_parts_sha256": _private_content_parts_hash(request),
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _private_content_parts_hash(request: LLMRequest) -> str | None:
    if not request.private_content_parts:
        return None
    payload = json.dumps(
        request.private_content_parts,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _safe_response_payload(payload: dict[str, Any]) -> dict[str, Any]:
    safe_payload = dict(payload)
    for private_key in PRIVATE_RESPONSE_KEYS:
        safe_payload.pop(private_key, None)
    return safe_payload


def _validation_payload(payload: dict[str, Any]) -> dict[str, Any]:
    validation_payload = dict(payload)
    for private_key in PRIVATE_ECHO_KEYS:
        validation_payload.pop(private_key, None)
    return validation_payload


def llm_usage_summary(conn: sqlite3.Connection) -> dict[str, Any]:
    total_row = conn.execute("SELECT COUNT(*) AS count FROM llm_requests").fetchone()
    total = int(total_row["count"]) if total_row else 0

    today_row = conn.execute(
        """
        SELECT COUNT(*) AS count
        FROM llm_requests
        WHERE date(created_at) = date('now')
        """
    ).fetchone()
    today = int(today_row["count"]) if today_row else 0

    by_feature_rows = conn.execute(
        """
        SELECT feature, status, COUNT(*) AS count
        FROM llm_requests
        GROUP BY feature, status
        ORDER BY feature, status
        """
    ).fetchall()

    by_feature: dict[str, dict[str, int]] = {}
    for row in by_feature_rows:
        feature = str(row["feature"])
        status = str(row["status"])
        by_feature.setdefault(feature, {})[status] = int(row["count"])

    recent_rows = conn.execute(
        """
        SELECT id, provider, model, feature, status, error, created_at
        FROM llm_requests
        ORDER BY id DESC
        LIMIT 25
        """
    ).fetchall()

    return {
        "total_requests": total,
        "requests_today": today,
        "by_feature": by_feature,
        "recent_requests": [
            {
                "id": int(row["id"]),
                "provider": row["provider"],
                "model": row["model"],
                "feature": row["feature"],
                "status": row["status"],
                "error": row["error"],
                "created_at": row["created_at"],
            }
            for row in recent_rows
        ],
    }
