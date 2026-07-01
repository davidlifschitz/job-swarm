from __future__ import annotations

SENSITIVE_ERROR_TERMS = (
    "password",
    "token",
    "secret",
    "authorization",
    "api_key",
    "apikey",
    "private_key",
    "access_key",
    "credential",
)


def sanitize_error_message(error: object, *, max_length: int = 500) -> str:
    if not error:
        return ""
    text = str(error).strip()
    normalized = text.casefold()
    if any(term in normalized for term in SENSITIVE_ERROR_TERMS):
        return "[redacted]"
    if len(text) > max_length:
        return text[:max_length]
    return text
