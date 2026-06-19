import json

import pytest
from pydantic import ValidationError

from ml_job_swarm.llm import (
    FitGateResponse,
    LLMRequest,
    ProfileDraftResponse,
    QuestionnaireResponse,
    ResumeRewriteResponse,
    VisionFallbackResponse,
    request_structured_response,
    record_llm_request,
)
from ml_job_swarm.store import connect, init_db


class FakeProvider:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def complete(self, request):
        self.calls.append(request)
        return self.responses.pop(0)


class NetworkLikeProvider:
    def complete(self, request):
        raise AssertionError("Tests must not use live network providers")


def test_profile_draft_schema_validates():
    response = ProfileDraftResponse.model_validate(
        {
            "headline": "ML engineer focused on AI infrastructure",
            "summary": "Production ML systems, platform engineering, and evaluation.",
            "keywords": ["python", "pytorch", "kubernetes"],
            "seniority_signals": ["senior", "platform ownership"],
        }
    )

    assert response.keywords == ["python", "pytorch", "kubernetes"]


def test_questionnaire_schema_validates_fixed_ids():
    response = QuestionnaireResponse.model_validate(
        {
            "questions": [
                {
                    "id": "role",
                    "prompt": "What role are you targeting?",
                    "options": ["ML Engineer", "AI Platform Engineer"],
                },
                {
                    "id": "level",
                    "prompt": "What level are you targeting?",
                    "options": ["Senior", "Staff"],
                },
                {
                    "id": "location",
                    "prompt": "Where do you want to work?",
                    "options": ["New York", "Remote US"],
                },
                {
                    "id": "work_mode",
                    "prompt": "Which work mode?",
                    "options": ["remote", "hybrid", "onsite"],
                },
                {
                    "id": "company_stage",
                    "prompt": "Which company stage?",
                    "options": ["startup", "growth", "enterprise"],
                },
            ]
        }
    )

    assert [question.id for question in response.questions] == [
        "role",
        "level",
        "location",
        "work_mode",
        "company_stage",
    ]

    with pytest.raises(ValidationError):
        QuestionnaireResponse.model_validate(
            {"questions": [{"id": "favorite_color", "prompt": "Bad", "options": ["x"]}]}
        )


def test_resume_rewrite_schema_validates():
    response = ResumeRewriteResponse.model_validate(
        {
            "section_id": 12,
            "replacement_text": "Built model-serving infrastructure for 80M requests/day.",
            "rationale": "Emphasizes production ownership.",
            "risk_flags": [],
        }
    )

    assert response.section_id == 12
    assert response.risk_flags == []


def test_fit_gate_requires_score_label_reasons_risks():
    response = FitGateResponse.model_validate(
        {
            "fit_score": 88,
            "label": "Strong fit",
            "reasons": ["ML systems match", "Python requirements match"],
            "risks": ["No explicit quant experience"],
            "recommendation": "Prioritize",
        }
    )

    assert response.fit_score == 88
    assert response.label == "Strong fit"

    with pytest.raises(ValidationError):
        FitGateResponse.model_validate(
            {"fit_score": 88, "label": "Strong fit", "reasons": ["missing risks"]}
        )


def test_vision_fallback_schema_validates_without_raw_page_images():
    response = VisionFallbackResponse.model_validate(
        {
            "extracted_text": "SUMMARY\nMachine learning engineer",
            "confidence": 0.82,
            "warnings": ["image_quality_low"],
        }
    )

    assert response.confidence == 0.82


def test_schema_failure_retries_once_then_records_failure():
    conn = connect()
    init_db(conn)
    provider = FakeProvider(
        [
            {"fit_score": "bad", "label": "Strong fit"},
            {"still": "invalid"},
        ]
    )
    request = LLMRequest(
        feature="fit_gate",
        schema_version="fit_gate.v1",
        model="openrouter/test-model",
        input_reference="job:1|profile:1",
        private_prompt="RAW PRIVATE RESUME TEXT should never be stored",
    )

    with pytest.raises(ValidationError):
        request_structured_response(conn, provider, request, FitGateResponse)

    rows = conn.execute(
        "SELECT model, schema_version, status, request_hash, response_json, error "
        "FROM llm_requests ORDER BY id"
    ).fetchall()
    assert len(rows) == 1
    row = dict(rows[0])
    assert row["status"] == "failed"
    assert row["model"] == "openrouter/test-model"
    assert row["schema_version"] == "fit_gate.v1"
    assert row["request_hash"]
    assert "RAW PRIVATE RESUME TEXT" not in json.dumps(row)
    assert len(provider.calls) == 2


def test_llm_request_metadata_omits_raw_private_prompt():
    conn = connect()
    init_db(conn)
    request = LLMRequest(
        feature="resume_rewrite",
        schema_version="resume_rewrite.v1",
        model="openrouter/test-model",
        input_reference="resume_asset:7|section:12",
        private_prompt="PRIVATE RESUME CONTENT AND PROMPT",
    )

    request_id = record_llm_request(
        conn,
        request,
        status="succeeded",
        response_payload={"section_id": 12},
    )

    row = conn.execute("SELECT * FROM llm_requests WHERE id = ?", (request_id,)).fetchone()
    persisted = json.dumps(dict(row), sort_keys=True)
    assert "PRIVATE RESUME CONTENT" not in persisted
    assert "resume_asset:7|section:12" in persisted
    assert row["provider"] == "openrouter"


def test_llm_request_hash_includes_private_content_parts_without_persisting_them():
    conn = connect()
    init_db(conn)
    first_request = LLMRequest(
        feature="resume_vision_fallback",
        schema_version="vision_fallback.v1",
        model="openrouter/test-model",
        input_reference="resume_asset:7",
        private_prompt="Extract resume text from attached pages.",
        private_content_parts=(
            {
                "type": "image_url",
                "image_url": {"url": "data:image/png;base64,PRIVATE_PAGE_ONE"},
            },
        ),
    )
    second_request = LLMRequest(
        feature="resume_vision_fallback",
        schema_version="vision_fallback.v1",
        model="openrouter/test-model",
        input_reference="resume_asset:7",
        private_prompt="Extract resume text from attached pages.",
        private_content_parts=(
            {
                "type": "image_url",
                "image_url": {"url": "data:image/png;base64,PRIVATE_PAGE_TWO"},
            },
        ),
    )

    first_id = record_llm_request(
        conn,
        first_request,
        status="succeeded",
        response_payload={"confidence": 0.9},
    )
    second_id = record_llm_request(
        conn,
        second_request,
        status="succeeded",
        response_payload={"confidence": 0.9},
    )

    rows = conn.execute(
        "SELECT request_hash, response_json FROM llm_requests WHERE id IN (?, ?)",
        (first_id, second_id),
    ).fetchall()
    assert rows[0]["request_hash"] != rows[1]["request_hash"]
    persisted = json.dumps([dict(row) for row in rows], sort_keys=True)
    assert "PRIVATE_PAGE_ONE" not in persisted
    assert "PRIVATE_PAGE_TWO" not in persisted


def test_success_metadata_strips_private_fields_from_provider_payload():
    conn = connect()
    init_db(conn)
    request = LLMRequest(
        feature="profile_draft",
        schema_version="profile_draft.v1",
        model="openrouter/test-model",
        input_reference="resume_asset:99",
        private_prompt="PRIVATE INPUT",
    )
    provider = FakeProvider(
        [
            {
                "headline": "AI platform engineer",
                "summary": "Builds reliable ML systems.",
                "keywords": ["python"],
                "seniority_signals": [],
                "raw_prompt": "PRIVATE INPUT",
                "resume_text": "PRIVATE RESUME",
            }
        ]
    )

    request_structured_response(conn, provider, request, ProfileDraftResponse)

    row = conn.execute("SELECT response_json FROM llm_requests").fetchone()
    persisted = row["response_json"]
    assert "PRIVATE INPUT" not in persisted
    assert "PRIVATE RESUME" not in persisted
    assert "resume_asset:99" in persisted


def test_vision_fallback_metadata_omits_extracted_resume_text():
    conn = connect()
    init_db(conn)
    request = LLMRequest(
        feature="resume_vision_fallback",
        schema_version="vision_fallback.v1",
        model="openrouter/test-vision",
        input_reference="resume_asset:101",
        private_prompt="PRIVATE PAGE IMAGE CONTENT",
    )
    provider = FakeProvider(
        [
            {
                "extracted_text": "PRIVATE VISION RESUME TEXT",
                "confidence": 0.91,
                "warnings": [],
            }
        ]
    )

    response = request_structured_response(
        conn, provider, request, VisionFallbackResponse
    )

    assert response.extracted_text == "PRIVATE VISION RESUME TEXT"
    row = conn.execute("SELECT response_json FROM llm_requests").fetchone()
    persisted = row["response_json"]
    assert "PRIVATE VISION RESUME TEXT" not in persisted
    assert "resume_asset:101" in persisted


def test_contract_tests_use_mocked_provider_only():
    conn = connect()
    init_db(conn)
    request = LLMRequest(
        feature="profile_draft",
        schema_version="profile_draft.v1",
        model="openrouter/test-model",
        input_reference="resume_asset:100",
        private_prompt="PRIVATE INPUT",
    )

    with pytest.raises(AssertionError, match="must not use live network"):
        request_structured_response(
            conn, NetworkLikeProvider(), request, ProfileDraftResponse
        )

    assert conn.execute("SELECT COUNT(*) FROM llm_requests").fetchone()[0] == 0
