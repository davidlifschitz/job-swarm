import json
from urllib import error

import pytest
from fastapi.testclient import TestClient

import ml_job_swarm.openrouter as openrouter
from ml_job_swarm.app import create_app
from ml_job_swarm.llm import LLMRequest
from ml_job_swarm.openrouter import (
    OpenRouterClientError,
    OpenRouterFitGateClient,
    OpenRouterProvider,
    OpenRouterResumeRewriteClient,
    configure_openrouter_clients_from_env,
)


class FakeTransport:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def __call__(self, url, headers, payload):
        self.calls.append({"url": url, "headers": headers, "payload": payload})
        return self.response


class _FakeHeaders:
    def get_content_charset(self):
        return "utf-8"


class _FakeOpenRouterResponse:
    headers = _FakeHeaders()

    def __init__(self, *, should_timeout_on_read: bool = False):
        self._should_timeout_on_read = should_timeout_on_read

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc, _tb):
        return False

    def read(self):
        if self._should_timeout_on_read:
            raise TimeoutError("read operation timed out")
        return json.dumps({"choices": [{"message": {"content": "{\"ok\": true}"}}]}).encode(
            "utf-8"
        )


def test_openrouter_provider_posts_chat_completion_json():
    transport = FakeTransport(
        {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "extracted_text": "SUMMARY\nML engineer",
                                "confidence": 0.91,
                                "warnings": [],
                            }
                        )
                    }
                }
            ]
        }
    )
    provider = OpenRouterProvider(
        api_key="unit-test-token",
        model="openrouter/test-vision",
        transport=transport,
        http_referer="https://example.test",
        app_title="ml-job-swarm-test",
    )

    result = provider.complete(
        LLMRequest(
            feature="resume_vision_fallback",
            schema_version="vision_fallback.v1",
            model="openrouter/test-vision",
            input_reference="resume_asset:1",
            private_prompt="PRIVATE RESUME CONTENT",
        )
    )

    assert result["confidence"] == 0.91
    call = transport.calls[0]
    assert call["url"] == "https://openrouter.ai/api/v1/chat/completions"
    assert call["headers"]["Authorization"] == "Bearer unit-test-token"
    assert call["headers"]["HTTP-Referer"] == "https://example.test"
    assert call["headers"]["X-OpenRouter-Title"] == "ml-job-swarm-test"
    assert call["payload"]["model"] == "openrouter/test-vision"
    assert call["payload"]["response_format"] == {"type": "json_object"}
    assert call["payload"]["messages"][-1]["content"] == "PRIVATE RESUME CONTENT"
    assert "unit-test-token" not in json.dumps(call["payload"])


def test_openrouter_provider_sends_private_content_parts():
    transport = FakeTransport(
        {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "extracted_text": "SUMMARY\nML engineer",
                                "confidence": 0.91,
                                "warnings": [],
                            }
                        )
                    }
                }
            ]
        }
    )
    provider = OpenRouterProvider(
        api_key="unit-test-token",
        model="openrouter/test-vision",
        transport=transport,
    )

    provider.complete(
        LLMRequest(
            feature="resume_vision_fallback",
            schema_version="vision_fallback.v1",
            model="openrouter/test-vision",
            input_reference="resume_asset:1",
            private_prompt="Extract resume text from attached page images.",
            private_content_parts=(
                {
                    "type": "image_url",
                    "image_url": {"url": "data:image/png;base64,cGFnZQ=="},
                },
            ),
        )
    )

    content = transport.calls[0]["payload"]["messages"][-1]["content"]
    assert content[0] == {
        "type": "text",
        "text": "Extract resume text from attached page images.",
    }
    assert content[1]["image_url"]["url"] == "data:image/png;base64,cGFnZQ=="


def test_openrouter_provider_rejects_malformed_response():
    provider = OpenRouterProvider(
        api_key="unit-test-token",
        model="openrouter/test",
        transport=FakeTransport({"choices": [{"message": {"content": "not json"}}]}),
    )

    with pytest.raises(OpenRouterClientError):
        provider.complete(
            LLMRequest(
                feature="fit_gate",
                schema_version="fit_gate.v1",
                model="openrouter/test",
                input_reference="job:1",
                private_prompt="Return JSON",
            )
        )


def test_openrouter_fit_gate_client_returns_schema_payload():
    transport = FakeTransport(
        {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "fit_score": 92,
                                "label": "Strong fit",
                                "reasons": ["Python and ML systems match"],
                                "risks": [],
                                "recommendation": "Show as a priority role.",
                            }
                        )
                    }
                }
            ]
        }
    )
    client = OpenRouterFitGateClient(
        api_key="unit-fit-token",
        model="openrouter/test-fit",
        transport=transport,
    )

    result = client.review_fit(
        {
            "job": {"title": "Machine Learning Engineer"},
            "company": {"name": "Example AI"},
            "target_profile": {"keywords": {"desired_titles": ["ML Engineer"]}},
            "rules_result": {"outcome": "review", "score": 86},
        }
    )

    assert result["fit_score"] == 92
    sent = json.dumps(transport.calls[0]["payload"])
    assert "Machine Learning Engineer" in sent
    assert "unit-fit-token" not in sent


def test_openrouter_resume_rewrite_client_returns_schema_payload():
    transport = FakeTransport(
        {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "section_id": 7,
                                "replacement_text": "Built ML platform serving 80M requests/day.",
                                "rationale": "Adds scale and impact.",
                                "risk_flags": [],
                            }
                        )
                    }
                }
            ]
        }
    )
    client = OpenRouterResumeRewriteClient(
        api_key="unit-rewrite-token",
        model="openrouter/test-rewrite",
        transport=transport,
    )

    result = client.rewrite_section(
        {
            "section_id": 7,
            "heading": "Experience",
            "section_type": "experience",
            "text": "Built ML systems.",
        }
    )

    assert result["replacement_text"].startswith("Built ML platform")
    sent = json.dumps(transport.calls[0]["payload"])
    assert "Built ML systems." in sent
    assert "unit-rewrite-token" not in sent


def test_openrouter_env_configures_app_clients(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "unit-env-token")
    monkeypatch.setenv("OPENROUTER_FIT_MODEL", "openrouter/fit-test")
    monkeypatch.setenv("OPENROUTER_RESUME_REWRITE_MODEL", "openrouter/rewrite-test")
    monkeypatch.setenv("OPENROUTER_VISION_MODEL", "openrouter/vision-test")

    app = create_app()

    assert app.state.fit_gate_client.model == "openrouter/fit-test"
    assert app.state.resume_rewrite_client.model == "openrouter/rewrite-test"
    assert app.state.vision_fallback_provider.model == "openrouter/vision-test"


def test_openrouter_env_without_key_preserves_disabled_clients(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    app = create_app()
    configure_openrouter_clients_from_env(app, environ={})
    client = TestClient(app)

    assert app.state.fit_gate_client is None
    assert app.state.resume_rewrite_client is None
    assert app.state.vision_fallback_provider is None
    response = client.post(
        "/dashboard/review-jobs",
        data={"target_profile_id": "1", "llm_consent": "on"},
    )
    assert response.status_code == 503


def test_openrouter_default_transport_retries_transient_urlopen_timeout(monkeypatch):
    seen_requests = []

    def fake_urlopen(request, timeout):
        seen_requests.append((request, timeout))
        if len(seen_requests) == 1:
            raise TimeoutError("timed out")
        return _FakeOpenRouterResponse()

    monkeypatch.setattr(openrouter.request, "urlopen", fake_urlopen)

    result = openrouter._urllib_transport(
        "https://openrouter.ai/api/v1/chat/completions",
        {"Authorization": "Bearer unit-token", "Content-Type": "application/json"},
        {"model": "openrouter/test", "messages": []},
    )

    assert result["choices"][0]["message"]["content"] == '{"ok": true}'
    assert len(seen_requests) == 2
    assert all(timeout == 60 for _request, timeout in seen_requests)


def test_openrouter_default_transport_retries_transient_read_timeout(monkeypatch):
    seen_requests = []

    def fake_urlopen(request, timeout):
        seen_requests.append((request, timeout))
        if len(seen_requests) == 1:
            return _FakeOpenRouterResponse(should_timeout_on_read=True)
        return _FakeOpenRouterResponse()

    monkeypatch.setattr(openrouter.request, "urlopen", fake_urlopen)

    result = openrouter._urllib_transport(
        "https://openrouter.ai/api/v1/chat/completions",
        {"Authorization": "Bearer unit-token", "Content-Type": "application/json"},
        {"model": "openrouter/test", "messages": []},
    )

    assert result["choices"][0]["message"]["content"] == '{"ok": true}'
    assert len(seen_requests) == 2


def test_openrouter_default_transport_does_not_retry_http_error(monkeypatch):
    seen_requests = []

    def fake_urlopen(request, timeout):
        seen_requests.append((request, timeout))
        raise error.HTTPError(
            request.full_url,
            401,
            "Unauthorized",
            hdrs=None,
            fp=None,
        )

    monkeypatch.setattr(openrouter.request, "urlopen", fake_urlopen)

    with pytest.raises(OpenRouterClientError, match="HTTP 401"):
        openrouter._urllib_transport(
            "https://openrouter.ai/api/v1/chat/completions",
            {"Authorization": "Bearer unit-token", "Content-Type": "application/json"},
            {"model": "openrouter/test", "messages": []},
        )

    assert len(seen_requests) == 1


def test_openrouter_rejects_non_https_base_url():
    with pytest.raises(OpenRouterClientError, match="https URL"):
        openrouter._validated_openrouter_base_url("http://openrouter.ai/api/v1")


def test_openrouter_rejects_disallowed_host():
    with pytest.raises(OpenRouterClientError, match="host is not allowed"):
        openrouter._validated_openrouter_base_url("https://evil.example/api/v1")


def test_openrouter_allows_default_host():
    assert (
        openrouter._validated_openrouter_base_url("https://openrouter.ai/api/v1")
        == "https://openrouter.ai/api/v1"
    )
