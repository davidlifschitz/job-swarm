from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from typing import Literal
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


PolicyMode = Literal["allowed", "blocked", "manual_link"]

RESTRICTED_DOMAINS = {
    "linkedin.com",
    "indeed.com",
}

SEARCH_PROXY_DOMAINS = {
    "bing.com",
    "duckduckgo.com",
    "google.com",
}

PUBLIC_ATS_DOMAINS = {
    "ashbyhq.com",
    "greenhouse.io",
    "jobs.ashbyhq.com",
    "jobs.lever.co",
    "lever.co",
    "myworkdayjobs.com",
    "smartrecruiters.com",
    "workable.com",
}

COMPANY_CAREER_TERMS = {
    "career",
    "careers",
    "job",
    "jobs",
    "join",
    "positions",
    "roles",
}

AUTH_TERMS = {
    "auth",
    "captcha",
    "login",
    "oauth",
    "password",
    "signin",
    "sign-in",
    "sso",
}


@dataclass(frozen=True)
class SourcePolicyResult:
    mode: PolicyMode
    reason: str
    normalized_url: str | None


def classify_source_url(url: str) -> SourcePolicyResult:
    normalized_url = _normalize_url(url)
    if normalized_url is None:
        return SourcePolicyResult("blocked", "invalid_url", None)

    parsed = urlsplit(normalized_url)
    host = parsed.hostname or ""
    if _is_blocked_fetch_host(host):
        return SourcePolicyResult("blocked", "private_or_reserved_host", None)
    domain = _registrable_domain(host)
    is_public_ats = any(
        _domain_matches(host, ats_domain) for ats_domain in PUBLIC_ATS_DOMAINS
    )
    haystack = " ".join(
        [
            host,
            parsed.path,
            parsed.query,
            *[value for _, value in parse_qsl(parsed.query, keep_blank_values=True)],
        ]
    ).lower()

    if domain in RESTRICTED_DOMAINS:
        return SourcePolicyResult("blocked", "restricted_source", None)
    if domain in SEARCH_PROXY_DOMAINS and _looks_like_search_proxy(parsed):
        return SourcePolicyResult("blocked", "search_result_proxy", None)
    if any(restricted in haystack for restricted in RESTRICTED_DOMAINS):
        return SourcePolicyResult("blocked", "restricted_source_proxy", None)
    if _looks_like_auth_or_captcha(parsed):
        return SourcePolicyResult("blocked", "auth_or_captcha", None)
    if is_public_ats:
        return SourcePolicyResult("allowed", "public_ats", normalized_url)
    if any(term in haystack for term in COMPANY_CAREER_TERMS):
        return SourcePolicyResult("allowed", "public_company_careers", normalized_url)

    return SourcePolicyResult("manual_link", "unknown_source", normalized_url)


def _normalize_url(url: str) -> str | None:
    raw = (url or "").strip()
    if not raw:
        return None
    if "://" not in raw:
        raw = f"https://{raw}"

    parsed = urlsplit(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None

    scheme = "https"
    netloc = parsed.netloc.lower()
    path = parsed.path or ""
    query = urlencode(sorted(parse_qsl(parsed.query, keep_blank_values=True)))
    return urlunsplit((scheme, netloc, path, query, ""))


def _registrable_domain(host: str) -> str:
    parts = host.lower().split(".")
    if len(parts) < 2:
        return host.lower()
    return ".".join(parts[-2:])


def _domain_matches(host: str, domain: str) -> bool:
    host = host.lower()
    domain = domain.lower()
    return host == domain or host.endswith(f".{domain}")


def _looks_like_auth_or_captcha(parsed) -> bool:
    path_segments = {segment.lower() for segment in parsed.path.split("/") if segment}
    query_keys = {
        key.lower() for key, _ in parse_qsl(parsed.query, keep_blank_values=True)
    }
    return bool(path_segments & AUTH_TERMS or query_keys & AUTH_TERMS)


def _is_blocked_fetch_host(host: str) -> bool:
    normalized = host.strip().lower().strip(".")
    if not normalized:
        return True
    if normalized in {"localhost", "metadata", "metadata.google.internal"}:
        return True
    if normalized.endswith(".localhost") or normalized.endswith(".local"):
        return True
    candidate = normalized.strip("[]")
    try:
        address = ipaddress.ip_address(candidate)
    except ValueError:
        return False
    return (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_reserved
        or address.is_multicast
        or address.is_unspecified
    )


MAX_FETCH_RESPONSE_BYTES = 5 * 1024 * 1024


def assert_safe_fetch_url(url: str) -> str:
    normalized = _normalize_url(url)
    if normalized is None:
        raise ValueError("invalid fetch URL")
    parsed = urlsplit(normalized)
    host = parsed.hostname or ""
    if _is_blocked_fetch_host(host):
        raise ValueError("blocked fetch host")
    return normalized


def _looks_like_search_proxy(parsed) -> bool:
    path = parsed.path.lower()
    query_keys = {key.lower() for key, _ in parse_qsl(parsed.query)}
    if path in {"", "/"} and "q" in query_keys:
        return True
    return path.startswith("/search") or path.startswith("/jobs/search")
