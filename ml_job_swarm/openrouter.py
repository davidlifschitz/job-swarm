from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping
from urllib import error, request

from fastapi import FastAPI

from ml_job_swarm.llm import LLMRequest


OPENROUTER_CHAT_COMPLETIONS_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_OPENROUTER_MODEL = "openrouter/auto"

JsonDict = dict[str, Any]
Transport = Callable[[str, Mapping[str, str], JsonDict], JsonDict]


class OpenRouterClientError(RuntimeError):
    pass


def configure_openrouter_clients_from_env(
    app: FastAPI,
    *,
    environ: Mapping[str, str] | None = None,
    transport: Transport | None = None,
) -> None:
    env = os.environ if environ is None else environ
    api_key = (env.get("OPENROUTER_API_KEY") or "").strip()
    if not api_key:
        return

    base_url = _validated_openrouter_base_url(
        (env.get("OPENROUTER_BASE_URL") or OPENROUTER_CHAT_COMPLETIONS_URL).strip()
    )
    http_referer = _optional_env(env, "OPENROUTER_HTTP_REFERER")
    app_title = _optional_env(env, "OPENROUTER_APP_TITLE")
    fit_model = _model_env(env, "OPENROUTER_FIT_MODEL")
    rewrite_model = _model_env(env, "OPENROUTER_RESUME_REWRITE_MODEL")
    vision_model = _model_env(env, "OPENROUTER_VISION_MODEL")

    app.state.fit_gate_client = OpenRouterFitGateClient(
        api_key=api_key,
        model=fit_model,
        base_url=base_url,
        transport=transport,
        http_referer=http_referer,
        app_title=app_title,
    )
    app.state.resume_rewrite_client = OpenRouterResumeRewriteClient(
        api_key=api_key,
        model=rewrite_model,
        base_url=base_url,
        transport=transport,
        http_referer=http_referer,
        app_title=app_title,
    )
    app.state.vision_fallback_provider = OpenRouterProvider(
        api_key=api_key,
        model=vision_model,
        base_url=base_url,
        transport=transport,
        http_referer=http_referer,
        app_title=app_title,
        schema_version="vision_fallback.v1",
    )


@dataclass
class OpenRouterProvider:
    api_key: str = field(repr=False)
    model: str = DEFAULT_OPENROUTER_MODEL
    base_url: str = OPENROUTER_CHAT_COMPLETIONS_URL
    transport: Transport | None = None
    http_referer: str | None = None
    app_title: str | None = None
    provider: str = "openrouter"
    schema_version: str = "openrouter_json.v1"

    def complete(self, request_payload: LLMRequest) -> JsonDict:
        return _OpenRouterJsonClient(
            api_key=self.api_key,
            base_url=self.base_url,
            transport=self.transport,
            http_referer=self.http_referer,
            app_title=self.app_title,
        ).complete_json(
            model=request_payload.model or self.model,
            messages=[
                _system_json_message(request_payload.feature, request_payload.schema_version),
                {
                    "role": "user",
                    "content": _user_content(
                        request_payload.private_prompt,
                        request_payload.private_content_parts,
                    ),
                },
            ],
        )


@dataclass
class OpenRouterFitGateClient:
    api_key: str = field(repr=False)
    model: str = DEFAULT_OPENROUTER_MODEL
    base_url: str = OPENROUTER_CHAT_COMPLETIONS_URL
    transport: Transport | None = None
    http_referer: str | None = None
    app_title: str | None = None
    provider: str = "openrouter"
    schema_version: str = "fit_gate.v1"

    def review_fit(self, payload: JsonDict) -> JsonDict:
        prompt = (
            "Review this job against the candidate profile and rules result. "
            "Return JSON with keys: fit_score, label, reasons, risks, recommendation. "
            "label must be one of: Strong fit, Possible fit, Mismatch risk, Filtered out.\n\n"
            f"{json.dumps(payload, sort_keys=True)}"
        )
        return self._client().complete_json(
            model=self.model,
            messages=[
                _system_json_message("fit_gate", self.schema_version),
                {"role": "user", "content": prompt},
            ],
        )

    def _client(self) -> "_OpenRouterJsonClient":
        return _OpenRouterJsonClient(
            api_key=self.api_key,
            base_url=self.base_url,
            transport=self.transport,
            http_referer=self.http_referer,
            app_title=self.app_title,
        )


@dataclass
class OpenRouterResumeRewriteClient:
    api_key: str = field(repr=False)
    model: str = DEFAULT_OPENROUTER_MODEL
    base_url: str = OPENROUTER_CHAT_COMPLETIONS_URL
    transport: Transport | None = None
    http_referer: str | None = None
    app_title: str | None = None
    provider: str = "openrouter"
    schema_version: str = "resume_rewrite.v1"

    def rewrite_section(self, payload: JsonDict) -> JsonDict:
        prompt = (
            "Rewrite only the selected resume section for the target role. "
            "Keep facts grounded in the supplied text. "
            "Return JSON with keys: section_id, replacement_text, rationale, risk_flags.\n\n"
            f"{json.dumps(payload, sort_keys=True)}"
        )
        return self._client().complete_json(
            model=self.model,
            messages=[
                _system_json_message("resume_rewrite", self.schema_version),
                {"role": "user", "content": prompt},
            ],
        )

    def _client(self) -> "_OpenRouterJsonClient":
        return _OpenRouterJsonClient(
            api_key=self.api_key,
            base_url=self.base_url,
            transport=self.transport,
            http_referer=self.http_referer,
            app_title=self.app_title,
        )


@dataclass(frozen=True)
class _OpenRouterJsonClient:
    api_key: str = field(repr=False)
    base_url: str
    transport: Transport | None = None
    http_referer: str | None = None
    app_title: str | None = None

    def complete_json(self, *, model: str, messages: list[JsonDict]) -> JsonDict:
        response_payload = self._send(
            {
                "model": model,
                "messages": messages,
                "response_format": {"type": "json_object"},
            }
        )
        content = _assistant_content(response_payload)
        if isinstance(content, dict):
            return content
        if not isinstance(content, str) or not content.strip():
            raise OpenRouterClientError("OpenRouter response did not include content")
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise OpenRouterClientError("OpenRouter response content was not JSON") from exc
        if not isinstance(parsed, dict):
            raise OpenRouterClientError("OpenRouter JSON response was not an object")
        return parsed

    def _send(self, payload: JsonDict) -> JsonDict:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if self.http_referer:
            headers["HTTP-Referer"] = self.http_referer
        if self.app_title:
            headers["X-OpenRouter-Title"] = self.app_title

        transport = self.transport or _urllib_transport
        return transport(self.base_url, headers, payload)


def _urllib_transport(url: str, headers: Mapping[str, str], payload: JsonDict) -> JsonDict:
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(url, data=body, headers=dict(headers), method="POST")
    try:
        raw_body = _read_openrouter_request(req).decode("utf-8")
    except error.HTTPError as exc:
        raise OpenRouterClientError(f"OpenRouter request failed: HTTP {exc.code}") from exc
    except (TimeoutError, error.URLError, OSError) as exc:
        raise OpenRouterClientError("OpenRouter request failed") from exc

    try:
        parsed = json.loads(raw_body)
    except json.JSONDecodeError as exc:
        raise OpenRouterClientError("OpenRouter returned non-JSON response") from exc
    if not isinstance(parsed, dict):
        raise OpenRouterClientError("OpenRouter returned non-object response")
    return parsed


def _read_openrouter_request(
    req: request.Request,
    *,
    timeout: int = 60,
    retries: int = 1,
) -> bytes:
    attempts = retries + 1
    for attempt in range(attempts):
        try:
            with request.urlopen(req, timeout=timeout) as response:
                return response.read()
        except error.HTTPError:
            raise
        except Exception as exc:
            if attempt == attempts - 1 or not _is_transient_openrouter_failure(exc):
                raise
    raise RuntimeError("unreachable OpenRouter retry state")


def _is_transient_openrouter_failure(exc: Exception) -> bool:
    if isinstance(exc, TimeoutError):
        return True
    reason = getattr(exc, "reason", None)
    if isinstance(reason, TimeoutError):
        return True
    return "timed out" in str(exc).casefold()


def _assistant_content(payload: JsonDict) -> Any:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise OpenRouterClientError("OpenRouter response missing choices")
    first = choices[0]
    if not isinstance(first, dict):
        raise OpenRouterClientError("OpenRouter response choice was invalid")
    message = first.get("message")
    if isinstance(message, dict):
        return message.get("content")
    if "text" in first:
        return first.get("text")
    raise OpenRouterClientError("OpenRouter response missing assistant message")


def _system_json_message(feature: str, schema_version: str) -> JsonDict:
    return {
        "role": "system",
        "content": (
            "You are a strict JSON API for ml-job-swarm. "
            f"Feature: {feature}. Schema: {schema_version}. "
            "Return only one JSON object. Do not include markdown."
        ),
    }


def _user_content(prompt: str, content_parts: tuple[JsonDict, ...]) -> str | list[JsonDict]:
    if not content_parts:
        return prompt
    return [{"type": "text", "text": prompt}, *content_parts]


def _optional_env(env: Mapping[str, str], key: str) -> str | None:
    value = (env.get(key) or "").strip()
    return value or None


def _model_env(env: Mapping[str, str], key: str) -> str:
    return (env.get(key) or DEFAULT_OPENROUTER_MODEL).strip() or DEFAULT_OPENROUTER_MODEL


def _validated_openrouter_base_url(base_url: str) -> str:
    from urllib.parse import urlsplit

    parsed = urlsplit(base_url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise OpenRouterClientError("OPENROUTER_BASE_URL must be an https URL")
    host = (parsed.hostname or "").lower()
    allowed_hosts = {"openrouter.ai", "api.openrouter.ai"}
    if not any(host == allowed or host.endswith(f".{allowed}") for allowed in allowed_hosts):
        raise OpenRouterClientError("OPENROUTER_BASE_URL host is not allowed")
    return base_url
