from __future__ import annotations

import html
import json
import re
from typing import Any, Callable
from urllib.error import HTTPError
from urllib.parse import quote, urlencode, urljoin, urlsplit
from urllib.request import Request, urlopen

from ml_job_swarm.ingest import (
    AdapterRegistry,
    JobSource,
    JobSourceAdapter,
    RawJob,
    RefreshError,
)
from ml_job_swarm.source_policy import classify_source_url


JsonFetcher = Callable[[str], Any]
JsonPostFetcher = Callable[[str, dict[str, object]], Any]
TextFetcher = Callable[[str], str]
_CAREERS_PATH_MARKERS = {
    "career",
    "career-openings",
    "careers",
    "jobs",
    "join",
    "join-us",
    "open-roles",
    "open-positions",
    "openings",
    "career-opportunities",
}
_CAREERS_HOST_PREFIXES = {"about", "careers", "jobs", "www"}
_GENERIC_GREENHOUSE_BOARD_TOKENS = {"job-boards"}
_JSON_LD_SCRIPT_RE = re.compile(
    r"<script[^>]+type=[\"']application/ld\+json(?:;[^\"']*)?[\"'][^>]*>(.*?)</script>",
    re.IGNORECASE | re.DOTALL,
)
_HTML_HREF_RE = re.compile(
    r"<a\b[^>]*\bhref\s*=\s*[\"']([^\"']+)[\"']",
    re.IGNORECASE,
)
_HTML_ANCHOR_RE = re.compile(
    r"<a\b[^>]*\bhref\s*=\s*[\"']([^\"']+)[\"'][^>]*>(.*?)</a>",
    re.IGNORECASE | re.DOTALL,
)
_EMBEDDED_ATS_URL_RE = re.compile(
    r"https?://(?:boards\.greenhouse\.io|jobs\.lever\.co|jobs\.ashbyhq\.com|"
    r"api\.smartrecruiters\.com|[^/\s\"'<>]+\.myworkdayjobs\.com|"
    r"apply\.workable\.com)/[^\s\"'<>]+",
    re.IGNORECASE,
)
_GENERIC_JOB_LINK_TEXT = {
    "apply",
    "apply now",
    "careers",
    "jobs",
    "learn more",
    "open positions",
    "open roles",
    "read more",
    "see open roles",
    "view jobs",
    "view open roles",
}
_JOB_INDEX_PATH_SEGMENTS = {
    "categories",
    "category",
    "departments",
    "department",
    "filters",
    "list",
    "locations",
    "location",
    "teams",
    "team",
}


class GreenhouseAdapter:
    def __init__(self, fetch_json: JsonFetcher | None = None):
        self._fetch_json = fetch_json or _default_fetch_json

    def fetch_jobs(self, source: JobSource) -> list[RawJob]:
        board_token = _greenhouse_board_token(source.url)
        if not board_token:
            raise RefreshError("Unsupported Greenhouse source URL", "manual_review_needed")
        payload = self._fetch_json(
            "https://boards-api.greenhouse.io/v1/boards/"
            f"{quote(board_token)}/jobs?content=true"
        )
        jobs = payload.get("jobs") if isinstance(payload, dict) else None
        if not isinstance(jobs, list):
            raise RefreshError("Malformed Greenhouse jobs payload", "manual_review_needed")
        return [_greenhouse_job(job) for job in jobs if isinstance(job, dict)]


class LeverAdapter:
    def __init__(self, fetch_json: JsonFetcher | None = None):
        self._fetch_json = fetch_json or _default_fetch_json

    def fetch_jobs(self, source: JobSource) -> list[RawJob]:
        site = _lever_site(source.url)
        if not site:
            raise RefreshError("Unsupported Lever source URL", "manual_review_needed")
        payload = self._fetch_json(
            f"https://api.lever.co/v0/postings/{quote(site)}?mode=json"
        )
        if not isinstance(payload, list):
            raise RefreshError("Malformed Lever postings payload", "manual_review_needed")
        return [_lever_job(job) for job in payload if isinstance(job, dict)]


class AshbyAdapter:
    def __init__(self, fetch_json: JsonFetcher | None = None):
        self._fetch_json = fetch_json or _default_fetch_json

    def fetch_jobs(self, source: JobSource) -> list[RawJob]:
        board_name = _ashby_board_name(source.url)
        if not board_name:
            raise RefreshError("Unsupported Ashby source URL", "manual_review_needed")
        payload = self._fetch_json(
            "https://api.ashbyhq.com/posting-api/job-board/"
            f"{quote(board_name)}?includeCompensation=false"
        )
        jobs = payload.get("jobs") if isinstance(payload, dict) else None
        if not isinstance(jobs, list):
            raise RefreshError("Malformed Ashby jobs payload", "manual_review_needed")
        return [
            _ashby_job(job)
            for job in jobs
            if isinstance(job, dict) and job.get("isListed") is not False
        ]


class CareersJsonLdAdapter:
    def __init__(
        self,
        fetch_text: TextFetcher | None = None,
        provider_adapters: dict[str, JobSourceAdapter] | None = None,
    ):
        self._fetch_text = fetch_text or _default_fetch_text
        self._provider_adapters = (
            provider_adapters
            if provider_adapters is not None
            else _default_careers_provider_adapters()
        )

    def fetch_jobs(self, source: JobSource) -> list[RawJob]:
        parsed = urlsplit(source.url)
        host = (parsed.hostname or "").lower()
        segments = [segment for segment in parsed.path.split("/") if segment]
        if not _looks_like_careers_page(host, segments):
            raise RefreshError(
                "Unsupported careers page source URL",
                "manual_review_needed",
            )
        page_text = self._fetch_text(source.url)
        jobs = [
            _jsonld_job(job, source.url)
            for job in _jsonld_jobpostings(page_text)
            if _string_or_none(job.get("title"))
        ]
        jobs.extend(self._provider_jobs(source, page_text))
        jobs.extend(_same_domain_job_link_jobs(page_text, source, jobs))
        return jobs

    def _provider_jobs(self, source: JobSource, page_text: str) -> list[RawJob]:
        jobs: list[RawJob] = []
        for provider_source in _public_provider_sources(page_text, source):
            adapter = self._provider_adapters.get(provider_source.source_type)
            if adapter is None:
                continue
            try:
                jobs.extend(adapter.fetch_jobs(provider_source))
            except RefreshError:
                continue
        return jobs


class WorkdayAdapter:
    def __init__(
        self,
        post_json: JsonPostFetcher | None = None,
        fetch_json: JsonFetcher | None = None,
    ):
        self._post_json = post_json or _default_post_json
        self._fetch_json = fetch_json or _default_fetch_json

    def fetch_jobs(self, source: JobSource) -> list[RawJob]:
        source_parts = _workday_source_parts(source.url)
        if not source_parts:
            raise RefreshError("Unsupported Workday source URL", "manual_review_needed")
        host, tenant, site = source_parts
        url = f"https://{host}/wday/cxs/{quote(tenant)}/{quote(site)}/jobs"
        jobs: list[RawJob] = []
        limit = 20
        offset = 0
        while True:
            body = {
                "appliedFacets": {},
                "limit": limit,
                "offset": offset,
                "searchText": "",
            }
            payload = self._post_json(url, body)
            postings = payload.get("jobPostings") if isinstance(payload, dict) else None
            if not isinstance(postings, list):
                raise RefreshError(
                    "Malformed Workday jobs payload",
                    "manual_review_needed",
                )
            for posting in postings:
                if not isinstance(posting, dict) or not _string_or_none(
                    posting.get("title")
                ):
                    continue
                jobs.append(
                    _workday_job(
                        self._hydrated_workday_posting(posting, host, tenant, site),
                        host,
                        site,
                    )
                )
            total = _int_or_none(payload.get("total")) if isinstance(payload, dict) else None
            offset += limit
            if not postings or len(postings) < limit or (
                total is not None and offset >= total
            ):
                break
        return jobs

    def _hydrated_workday_posting(
        self,
        posting: dict[str, Any],
        host: str,
        tenant: str,
        site: str,
    ) -> dict[str, Any]:
        detail_url = _workday_detail_api_url(
            host,
            tenant,
            site,
            _string_or_none(posting.get("externalPath")),
        )
        if detail_url is None:
            return posting
        try:
            detail = self._fetch_json(detail_url)
        except Exception:
            return posting
        if not isinstance(detail, dict):
            return posting
        return posting | _workday_detail_fields(detail)


class SmartRecruitersAdapter:
    def __init__(self, fetch_json: JsonFetcher | None = None):
        self._fetch_json = fetch_json or _default_fetch_json

    def fetch_jobs(self, source: JobSource) -> list[RawJob]:
        company_identifier = _smartrecruiters_company_identifier(source.url)
        if not company_identifier:
            raise RefreshError(
                "Unsupported SmartRecruiters source URL",
                "manual_review_needed",
            )

        jobs: list[RawJob] = []
        limit = 100
        offset = 0
        while True:
            list_url = _smartrecruiters_list_url(company_identifier, limit, offset)
            payload = self._fetch_json(list_url)
            postings = payload.get("content") if isinstance(payload, dict) else None
            if not isinstance(postings, list):
                raise RefreshError(
                    "Malformed SmartRecruiters postings payload",
                    "manual_review_needed",
                )
            for posting in postings:
                if not isinstance(posting, dict):
                    continue
                posting_id = _string_or_none(posting.get("id")) or _string_or_none(
                    posting.get("uuid")
                )
                if posting_id:
                    detail = self._fetch_json(
                        "https://api.smartrecruiters.com/v1/companies/"
                        f"{quote(company_identifier)}/postings/{quote(posting_id)}"
                    )
                    if isinstance(detail, dict):
                        posting = {**posting, **detail}
                if _string_or_none(posting.get("name")) or _string_or_none(
                    posting.get("title")
                ):
                    jobs.append(_smartrecruiters_job(posting, company_identifier))

            total = _int_or_none(payload.get("totalFound")) if isinstance(payload, dict) else None
            offset += limit
            if not postings or len(postings) < limit or (
                total is not None and offset >= total
            ):
                break
        return jobs


class WorkableAdapter:
    def __init__(self, fetch_json: JsonFetcher | None = None):
        self._fetch_json = fetch_json or _default_fetch_json

    def fetch_jobs(self, source: JobSource) -> list[RawJob]:
        account = _workable_account_subdomain(source.url)
        if not account:
            raise RefreshError("Unsupported Workable source URL", "manual_review_needed")
        payload = self._fetch_json(
            f"https://www.workable.com/api/accounts/{quote(account)}?details=true"
        )
        jobs = payload.get("jobs") if isinstance(payload, dict) else None
        if not isinstance(jobs, list):
            raise RefreshError("Malformed Workable jobs payload", "manual_review_needed")
        return [
            _workable_job(job, account)
            for job in jobs
            if isinstance(job, dict) and _string_or_none(job.get("title"))
        ]


def public_ats_registry() -> AdapterRegistry:
    return AdapterRegistry(
        {
            "greenhouse": GreenhouseAdapter(),
            "lever": LeverAdapter(),
            "ashby": AshbyAdapter(),
            "careers": CareersJsonLdAdapter(),
            "workday": WorkdayAdapter(),
            "smartrecruiters": SmartRecruitersAdapter(),
            "workable": WorkableAdapter(),
        }
    )


def _default_careers_provider_adapters() -> dict[str, JobSourceAdapter]:
    return {
        "greenhouse": GreenhouseAdapter(),
        "lever": LeverAdapter(),
        "ashby": AshbyAdapter(),
        "workday": WorkdayAdapter(),
        "smartrecruiters": SmartRecruitersAdapter(),
        "workable": WorkableAdapter(),
    }


def _default_fetch_json(url: str) -> Any:
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 ml-job-swarm-public-ats/1.0",
        },
    )
    try:
        raw, charset = _read_url_request(request)
        return json.loads(raw.decode(charset))
    except HTTPError as exc:
        raise RefreshError(
            f"Public ATS fetch failed: {exc}",
            _http_error_event_type(exc),
            status_code=exc.code,
        ) from exc
    except Exception as exc:
        event_type = "timeout" if _is_transient_timeout(exc) else "blocked_response"
        raise RefreshError(f"Public ATS fetch failed: {exc}", event_type) from exc


def _default_fetch_text(url: str) -> str:
    request = Request(
        url,
        headers={
            "Accept": "text/html,application/xhtml+xml",
            "User-Agent": "Mozilla/5.0 ml-job-swarm-public-careers/1.0",
        },
    )
    try:
        raw, charset = _read_url_request(request)
        return raw.decode(charset, errors="replace")
    except HTTPError as exc:
        raise RefreshError(
            f"Public careers page fetch failed: {exc}",
            _http_error_event_type(exc),
            status_code=exc.code,
        ) from exc
    except Exception as exc:
        event_type = "timeout" if _is_transient_timeout(exc) else "blocked_response"
        raise RefreshError(
            f"Public careers page fetch failed: {exc}",
            event_type,
        ) from exc


def _default_post_json(url: str, body: dict[str, object]) -> Any:
    request = Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 ml-job-swarm-public-ats/1.0",
        },
        method="POST",
    )
    try:
        raw, charset = _read_url_request(request)
        return json.loads(raw.decode(charset))
    except HTTPError as exc:
        raise RefreshError(
            f"Public ATS fetch failed: {exc}",
            _http_error_event_type(exc),
            status_code=exc.code,
        ) from exc
    except Exception as exc:
        event_type = "timeout" if _is_transient_timeout(exc) else "blocked_response"
        raise RefreshError(f"Public ATS fetch failed: {exc}", event_type) from exc


def _read_url_request(
    request: Request,
    *,
    timeout: int = 20,
    retries: int = 1,
) -> tuple[bytes, str]:
    attempts = retries + 1
    for attempt in range(attempts):
        try:
            with urlopen(request, timeout=timeout) as response:
                charset = response.headers.get_content_charset() or "utf-8"
                return response.read(), charset
        except Exception as exc:
            if attempt == attempts - 1 or not _is_transient_timeout(exc):
                raise
    raise RuntimeError("unreachable public fetch retry state")


def _is_transient_timeout(exc: Exception) -> bool:
    if isinstance(exc, TimeoutError):
        return True
    reason = getattr(exc, "reason", None)
    if isinstance(reason, TimeoutError):
        return True
    return "timed out" in str(exc).casefold()


def _http_error_event_type(exc: HTTPError) -> str:
    if exc.code == 429:
        return "rate_limited"
    return "blocked_response"


def _greenhouse_board_token(url: str) -> str | None:
    parsed = urlsplit(url)
    host = (parsed.hostname or "").lower()
    segments = [segment for segment in parsed.path.split("/") if segment]
    if host == "boards.greenhouse.io" and segments:
        return segments[0]
    if host.endswith("greenhouse.io") and segments and segments[0] == "boards":
        return segments[1] if len(segments) > 1 else None
    if _looks_like_careers_page(host, segments):
        return _host_board_token(host)
    return None


def _looks_like_careers_page(host: str, segments: list[str]) -> bool:
    labels = [label for label in host.split(".") if label]
    if host.endswith(".jobs") or host.endswith(".careers"):
        return True
    split_segments = {
        part
        for segment in segments
        for part in re.split(r"[-_]+", segment.casefold())
        if part
    }
    return any(segment.casefold() in _CAREERS_PATH_MARKERS for segment in segments) or (
        "careers" in split_segments
    ) or (
        bool(labels) and labels[0].casefold() in {"careers", "jobs"}
    )


def _host_board_token(host: str) -> str | None:
    if not host:
        return None
    labels = [
        label
        for label in host.split(".")
        if label and label.casefold() not in _CAREERS_HOST_PREFIXES
    ]
    if not labels:
        return None
    if len(labels) >= 2 and len(labels[0]) == 1 and len(labels[1]) <= 3:
        return f"{labels[0]}{labels[1]}"
    return labels[0]


def _lever_site(url: str) -> str | None:
    parsed = urlsplit(url)
    host = (parsed.hostname or "").lower()
    segments = [segment for segment in parsed.path.split("/") if segment]
    if host in {"jobs.lever.co", "jobs.eu.lever.co"} and segments:
        return segments[0]
    if _looks_like_careers_page(host, segments):
        return _host_board_token(host)
    return None


def _ashby_board_name(url: str) -> str | None:
    parsed = urlsplit(url)
    host = (parsed.hostname or "").lower()
    segments = [segment for segment in parsed.path.split("/") if segment]
    if host in {"jobs.ashbyhq.com", "jobs.eu.ashbyhq.com"} and segments:
        return segments[0]
    if host and host not in {"ashbyhq.com", "www.ashbyhq.com"}:
        labels = [label for label in host.split(".") if label and label != "www"]
        if labels and any(segment.casefold() == "careers" for segment in segments):
            return labels[0]
    return None


def _workday_source_parts(url: str) -> tuple[str, str, str] | None:
    parsed = urlsplit(url)
    host = (parsed.hostname or "").lower()
    if not host.endswith(".myworkdayjobs.com"):
        return None
    labels = [label for label in host.split(".") if label]
    if len(labels) < 3:
        return None
    tenant = labels[0]
    segments = [segment for segment in parsed.path.split("/") if segment]
    if segments and _looks_like_locale_segment(segments[0]):
        segments = segments[1:]
    if not segments:
        return None
    return host, tenant, segments[0]


def _looks_like_locale_segment(segment: str) -> bool:
    return bool(re.fullmatch(r"[a-z]{2}[-_][a-z]{2}", segment.casefold()))


def _smartrecruiters_company_identifier(url: str) -> str | None:
    parsed = urlsplit(url)
    host = (parsed.hostname or "").lower()
    segments = [segment for segment in parsed.path.split("/") if segment]
    if host in {"jobs.smartrecruiters.com", "careers.smartrecruiters.com"}:
        return segments[0] if segments else None
    if host == "api.smartrecruiters.com" and len(segments) >= 4:
        if segments[0] == "v1" and segments[1] == "companies":
            return segments[2]
    return None


def _workable_account_subdomain(url: str) -> str | None:
    parsed = urlsplit(url)
    host = (parsed.hostname or "").lower()
    segments = [segment for segment in parsed.path.split("/") if segment]
    if host == "apply.workable.com":
        if segments and segments[0] != "j":
            return segments[0]
        return None
    if host == "www.workable.com" and len(segments) >= 3:
        if segments[0] == "api" and segments[1] == "accounts":
            return segments[2]
        return None
    if host.endswith(".workable.com") and host not in {
        "www.workable.com",
        "apply.workable.com",
    }:
        labels = [label for label in host.split(".") if label]
        return labels[0] if labels else None
    return None


def _smartrecruiters_list_url(
    company_identifier: str,
    limit: int,
    offset: int,
) -> str:
    query = urlencode(
        {
            "limit": limit,
            "offset": offset,
            "destination": "PUBLIC",
        }
    )
    return (
        "https://api.smartrecruiters.com/v1/companies/"
        f"{quote(company_identifier)}/postings?{query}"
    )


def _jsonld_jobpostings(page_text: str) -> list[dict[str, Any]]:
    postings: list[dict[str, Any]] = []
    for match in _JSON_LD_SCRIPT_RE.finditer(page_text):
        raw_json = html.unescape(match.group(1)).strip()
        if not raw_json:
            continue
        try:
            payload = json.loads(raw_json)
        except json.JSONDecodeError:
            continue
        postings.extend(_collect_jsonld_jobpostings(payload))
    return postings


def _public_provider_sources(page_text: str, source: JobSource) -> list[JobSource]:
    provider_sources: list[JobSource] = []
    seen: set[tuple[str, str]] = set()
    candidate_urls = list(_html_links(page_text, source.url))
    candidate_urls.extend(_embedded_ats_urls(page_text))
    for linked_url in candidate_urls:
        policy = classify_source_url(linked_url)
        if policy.mode != "allowed" or not policy.normalized_url:
            continue
        provider_source = _provider_source(policy.normalized_url, source.company_id)
        if provider_source is None:
            continue
        key = (provider_source.source_type, provider_source.url)
        if key in seen:
            continue
        seen.add(key)
        provider_sources.append(provider_source)
    return provider_sources


def _embedded_ats_urls(page_text: str) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()
    for match in _EMBEDDED_ATS_URL_RE.finditer(page_text):
        raw_url = html.unescape(match.group(0)).strip().rstrip(".,;)")
        if not raw_url or raw_url in seen:
            continue
        seen.add(raw_url)
        urls.append(raw_url)
    return urls


def _html_links(page_text: str, base_url: str) -> list[str]:
    links: list[str] = []
    for match in _HTML_HREF_RE.finditer(page_text):
        raw_href = html.unescape(match.group(1)).strip()
        if not raw_href or raw_href.startswith("#"):
            continue
        href_scheme = raw_href.split(":", 1)[0].casefold()
        if ":" in raw_href and href_scheme not in {"http", "https"}:
            continue
        links.append(urljoin(base_url, raw_href))
    return links


def _html_anchor_links(page_text: str, base_url: str) -> list[tuple[str, str]]:
    links: list[tuple[str, str]] = []
    for match in _HTML_ANCHOR_RE.finditer(page_text):
        raw_href = html.unescape(match.group(1)).strip()
        if not raw_href or raw_href.startswith("#"):
            continue
        href_scheme = raw_href.split(":", 1)[0].casefold()
        if ":" in raw_href and href_scheme not in {"http", "https"}:
            continue
        label = _clean_job_link_title(match.group(2))
        if label is None:
            continue
        links.append((urljoin(base_url, raw_href), label))
    return links


def _same_domain_job_link_jobs(
    page_text: str,
    source: JobSource,
    existing_jobs: list[RawJob],
) -> list[RawJob]:
    source_host = (urlsplit(source.url).hostname or "").lower()
    source_url = _canonical_url(source.url)
    seen_urls = {
        _canonical_url(job.apply_url or job.source_url or "")
        for job in existing_jobs
        if job.apply_url or job.source_url
    }
    jobs: list[RawJob] = []
    for linked_url, title in _html_anchor_links(page_text, source.url):
        canonical_url = _canonical_url(linked_url)
        parsed = urlsplit(canonical_url)
        if (parsed.hostname or "").lower() != source_host:
            continue
        if canonical_url == source_url or canonical_url in seen_urls:
            continue
        segments = [segment for segment in parsed.path.split("/") if segment]
        if not _looks_like_job_detail_path(segments):
            continue
        seen_urls.add(canonical_url)
        jobs.append(
            RawJob(
                external_id="/".join(segments) or canonical_url,
                title=title,
                apply_url=canonical_url,
                source_url=canonical_url,
            )
        )
    return jobs


def _looks_like_job_detail_path(segments: list[str]) -> bool:
    if len(segments) < 2:
        return False
    markers = {"career", "careers", "job", "jobs", "open-roles", "positions"}
    normalized = [segment.casefold() for segment in segments]
    if any("{{" in segment or "}}" in segment for segment in normalized):
        return False
    if any(segment in _JOB_INDEX_PATH_SEGMENTS for segment in normalized):
        return False
    if not any(segment in markers for segment in normalized[:-1]):
        return False
    leaf = normalized[-1]
    if leaf in markers or leaf in {"search", "results", "all", "openings"}:
        return False
    return True


def _clean_job_link_title(value: object) -> str | None:
    text = _clean_text(value)
    if not text:
        return None
    if "{{" in text or "}}" in text:
        return None
    text = re.sub(r"\s+read more$", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"\s+apply now$", "", text, flags=re.IGNORECASE).strip()
    if not text or text.casefold() in _GENERIC_JOB_LINK_TEXT:
        return None
    return text


def _canonical_url(url: str) -> str:
    parsed = urlsplit(url)
    path = parsed.path.rstrip("/") or "/"
    return parsed._replace(path=path, query="", fragment="").geturl()


def _provider_source(url: str, company_id: int) -> JobSource | None:
    parsed = urlsplit(url)
    host = (parsed.hostname or "").lower()
    if _host_matches(host, "greenhouse.io"):
        board_token = _greenhouse_board_token(url)
        if board_token and board_token not in _GENERIC_GREENHOUSE_BOARD_TOKENS:
            return _provider_job_source(
                company_id, f"https://boards.greenhouse.io/{board_token}", "greenhouse"
            )
    if _host_matches(host, "lever.co"):
        site = _lever_site(url)
        if site:
            return _provider_job_source(
                company_id, f"https://jobs.lever.co/{site}", "lever"
            )
    if _host_matches(host, "ashbyhq.com"):
        board_name = _ashby_board_name(url)
        if board_name:
            return _provider_job_source(
                company_id, f"https://jobs.ashbyhq.com/{board_name}", "ashby"
            )
    source_parts = _workday_source_parts(url)
    if source_parts:
        host, _tenant, site = source_parts
        return _provider_job_source(company_id, f"https://{host}/{site}", "workday")
    if _host_matches(host, "smartrecruiters.com"):
        company_identifier = _smartrecruiters_company_identifier(url)
        if company_identifier:
            return _provider_job_source(
                company_id,
                f"https://jobs.smartrecruiters.com/{company_identifier}",
                "smartrecruiters",
            )
    if _host_matches(host, "workable.com"):
        account = _workable_account_subdomain(url)
        if account:
            return _provider_job_source(
                company_id, f"https://apply.workable.com/{account}/", "workable"
            )
    return None


def _provider_job_source(company_id: int, url: str, source_type: str) -> JobSource:
    return JobSource(
        id=0,
        company_id=company_id,
        url=url,
        source_type=source_type,
        policy_mode="allowed",
        review_status="reviewed",
    )


def _host_matches(host: str, domain: str) -> bool:
    return host == domain or host.endswith(f".{domain}")


def _collect_jsonld_jobpostings(value: object) -> list[dict[str, Any]]:
    if isinstance(value, list):
        postings: list[dict[str, Any]] = []
        for item in value:
            postings.extend(_collect_jsonld_jobpostings(item))
        return postings
    if not isinstance(value, dict):
        return []
    postings = []
    graph = value.get("@graph")
    if graph is not None:
        postings.extend(_collect_jsonld_jobpostings(graph))
    if _jsonld_type_includes(value.get("@type"), "JobPosting"):
        postings.append(value)
    return postings


def _jsonld_type_includes(value: object, expected: str) -> bool:
    if isinstance(value, list):
        return any(_jsonld_type_includes(item, expected) for item in value)
    text = str(value or "").casefold()
    expected_text = expected.casefold()
    return (
        text == expected_text
        or text.endswith(f"/{expected_text}")
        or text.endswith(f"#{expected_text}")
    )


def _greenhouse_job(job: dict[str, Any]) -> RawJob:
    departments = job.get("departments")
    offices = job.get("offices")
    return RawJob(
        external_id=str(job["id"]) if job.get("id") is not None else None,
        title=str(job.get("title") or "").strip(),
        department=_first_name(departments),
        location_text=_nested_name(job.get("location")) or _first_location(offices),
        description_text=_clean_text(job.get("content")),
        apply_url=str(job.get("absolute_url") or ""),
        source_url=str(job.get("absolute_url") or ""),
    )


def _lever_job(job: dict[str, Any]) -> RawJob:
    categories = job.get("categories") if isinstance(job.get("categories"), dict) else {}
    return RawJob(
        external_id=str(job.get("id") or "") or None,
        title=str(job.get("text") or "").strip(),
        department=_string_or_none(categories.get("team")),
        location_text=_string_or_none(categories.get("location")),
        employment_type=_string_or_none(categories.get("commitment")),
        description_text=_clean_text(job.get("descriptionPlain") or job.get("description")),
        requirements_text=_lever_lists_text(job.get("lists")),
        apply_url=str(job.get("hostedUrl") or ""),
        source_url=str(job.get("hostedUrl") or ""),
    )


def _ashby_job(job: dict[str, Any]) -> RawJob:
    job_url = str(job.get("jobUrl") or "")
    apply_url = str(job.get("applyUrl") or job_url)
    return RawJob(
        external_id=job_url or str(job.get("id") or "") or None,
        title=str(job.get("title") or "").strip(),
        department=_string_or_none(job.get("department"))
        or _string_or_none(job.get("team")),
        location_text=_string_or_none(job.get("location"))
        or _ashby_postal_location(job.get("address")),
        remote_mode=_normalized_workplace_type(job.get("workplaceType")),
        employment_type=_string_or_none(job.get("employmentType")),
        description_text=_clean_text(
            job.get("descriptionPlain") or job.get("descriptionHtml")
        ),
        apply_url=apply_url,
        source_url=job_url or apply_url,
    )


def _jsonld_job(job: dict[str, Any], fallback_url: str) -> RawJob:
    job_url = _string_or_none(job.get("url")) or fallback_url
    return RawJob(
        external_id=_jsonld_identifier(job.get("identifier")) or job_url,
        title=str(job.get("title") or "").strip(),
        department=_string_or_none(job.get("occupationalCategory")),
        location_text=_jsonld_location(job.get("jobLocation")),
        remote_mode=_jsonld_remote_mode(job.get("jobLocationType")),
        employment_type=_jsonld_joined_text(job.get("employmentType")),
        description_text=_clean_text(job.get("description")),
        requirements_text=_jsonld_requirements(job),
        apply_url=job_url,
        source_url=job_url,
    )


def _workday_job(job: dict[str, Any], host: str, site: str) -> RawJob:
    external_path = _string_or_none(job.get("externalPath"))
    source_url = _workday_job_url(host, site, external_path)
    return RawJob(
        external_id=_string_or_none(job.get("requisitionId"))
        or _string_or_none(job.get("jobReqId"))
        or _workday_requisition_from_bullets(job.get("bulletFields"))
        or _workday_external_id(external_path),
        title=str(job.get("title") or "").strip(),
        location_text=_string_or_none(job.get("locationsText")),
        employment_type=_string_or_none(job.get("timeType"))
        or _string_or_none(job.get("jobType"))
        or _workday_bullet_text(job.get("bulletFields")),
        description_text=_clean_text(
            job.get("jobDescription")
            or job.get("jobDescriptionSummary")
            or job.get("description")
        ),
        requirements_text=_clean_text(
            job.get("qualifications")
            or job.get("requirements")
            or job.get("hiringRequirements")
        ),
        apply_url=source_url,
        source_url=source_url,
    )


def _workday_detail_api_url(
    host: str,
    tenant: str,
    site: str,
    external_path: str | None,
) -> str | None:
    if not external_path:
        return None
    path = external_path if external_path.startswith("/") else f"/{external_path}"
    return f"https://{host}/wday/cxs/{quote(tenant)}/{quote(site)}{path}"


def _workday_detail_fields(detail: dict[str, Any]) -> dict[str, Any]:
    info = detail.get("jobPostingInfo")
    if isinstance(info, dict):
        fields = dict(info)
    else:
        fields = dict(detail)
    for key in ("hiringRequirements", "qualifications", "requirements"):
        if key in detail and key not in fields:
            fields[key] = detail[key]
    return fields


def _workday_job_url(host: str, site: str, external_path: str | None) -> str:
    base_url = f"https://{host}/{site}"
    if not external_path:
        return base_url
    if external_path.startswith("/"):
        return f"{base_url}{external_path}"
    return f"{base_url}/{external_path}"


def _workday_external_id(external_path: str | None) -> str | None:
    if not external_path:
        return None
    return external_path.rstrip("/").rsplit("/", 1)[-1] or None


def _workday_bullet_text(value: object) -> str | None:
    if not isinstance(value, list):
        return None
    return ", ".join(str(item).strip() for item in value if str(item).strip()) or None


def _workday_requisition_from_bullets(value: object) -> str | None:
    if not isinstance(value, list):
        return None
    for item in value:
        text = str(item).strip()
        if re.fullmatch(r"[A-Z]{1,4}\d{4,}", text):
            return text
    return None


def _smartrecruiters_job(job: dict[str, Any], company_identifier: str) -> RawJob:
    posting_id = _string_or_none(job.get("id")) or _string_or_none(job.get("uuid"))
    fallback_url = (
        f"https://jobs.smartrecruiters.com/{quote(company_identifier)}/{quote(posting_id)}"
        if posting_id
        else f"https://jobs.smartrecruiters.com/{quote(company_identifier)}"
    )
    source_url = (
        _string_or_none(job.get("postingUrl"))
        or _string_or_none(job.get("applyUrl"))
        or fallback_url
    )
    return RawJob(
        external_id=posting_id,
        title=str(job.get("name") or job.get("title") or "").strip(),
        department=_label_or_text(job.get("department"))
        or _label_or_text(job.get("function")),
        location_text=_smartrecruiters_location(job.get("location")),
        remote_mode=_smartrecruiters_remote_mode(job.get("location")),
        employment_type=_label_or_text(job.get("typeOfEmployment")),
        seniority=_label_or_text(job.get("experienceLevel")),
        description_text=_smartrecruiters_description(job.get("jobAd")),
        requirements_text=_smartrecruiters_qualifications(job.get("jobAd")),
        apply_url=_string_or_none(job.get("applyUrl")) or source_url,
        source_url=source_url,
    )


def _workable_job(job: dict[str, Any], account: str) -> RawJob:
    source_url = (
        _string_or_none(job.get("url"))
        or _string_or_none(job.get("shortlink"))
        or f"https://apply.workable.com/{quote(account)}/"
    )
    apply_url = (
        _string_or_none(job.get("application_url"))
        or _string_or_none(job.get("shortlink"))
        or source_url
    )
    return RawJob(
        external_id=_string_or_none(job.get("shortcode"))
        or _string_or_none(job.get("code"))
        or source_url,
        title=str(job.get("title") or "").strip(),
        department=_string_or_none(job.get("department"))
        or _string_or_none(job.get("function")),
        location_text=_workable_location(job),
        remote_mode=_workable_remote_mode(job),
        employment_type=_string_or_none(job.get("employment_type")),
        seniority=_string_or_none(job.get("experience")),
        description_text=_clean_text(job.get("description")),
        requirements_text=_clean_text(job.get("requirements")),
        apply_url=apply_url,
        source_url=source_url,
    )


def _jsonld_identifier(value: object) -> str | None:
    if isinstance(value, dict):
        return _string_or_none(value.get("value")) or _string_or_none(value.get("name"))
    return _string_or_none(value)


def _jsonld_location(value: object) -> str | None:
    if isinstance(value, list):
        return "; ".join(
            location for item in value if (location := _jsonld_location(item))
        ) or None
    if isinstance(value, dict):
        name = _string_or_none(value.get("name"))
        address = value.get("address")
        if isinstance(address, dict):
            parts = [
                _string_or_none(address.get("addressLocality")),
                _string_or_none(address.get("addressRegion")),
                _string_or_none(address.get("addressCountry")),
            ]
            return ", ".join(part for part in parts if part) or name
        return name
    return _string_or_none(value)


def _jsonld_remote_mode(value: object) -> str | None:
    text = _jsonld_joined_text(value)
    if not text:
        return None
    normalized = text.casefold().replace("_", "").replace("-", "")
    if normalized in {"telecommute", "remote"}:
        return "remote"
    return text


def _jsonld_requirements(job: dict[str, Any]) -> str | None:
    parts = [
        _jsonld_joined_text(job.get("qualifications")),
        _jsonld_joined_text(job.get("skills")),
        _jsonld_joined_text(job.get("experienceRequirements")),
    ]
    return "\n".join(part for part in parts if part) or None


def _jsonld_joined_text(value: object) -> str | None:
    if isinstance(value, list):
        return ", ".join(
            text for item in value if (text := _jsonld_joined_text(item))
        ) or None
    if isinstance(value, dict):
        return _string_or_none(value.get("name")) or _string_or_none(value.get("value"))
    return _string_or_none(value)


def _ashby_postal_location(value: object) -> str | None:
    if not isinstance(value, dict):
        return None
    postal = value.get("postalAddress")
    if not isinstance(postal, dict):
        return None
    parts = [
        _string_or_none(postal.get("addressLocality")),
        _string_or_none(postal.get("addressRegion")),
        _string_or_none(postal.get("addressCountry")),
    ]
    return ", ".join(part for part in parts if part) or None


def _normalized_workplace_type(value: object) -> str | None:
    text = _string_or_none(value)
    if not text:
        return None
    normalized = text.casefold().replace("_", "").replace("-", "")
    if normalized == "onsite":
        return "onsite"
    if normalized == "remote":
        return "remote"
    if normalized == "hybrid":
        return "hybrid"
    return text


def _smartrecruiters_location(value: object) -> str | None:
    if not isinstance(value, dict):
        return _string_or_none(value)
    city = _string_or_none(value.get("city"))
    region = _string_or_none(value.get("region"))
    country = _string_or_none(value.get("country"))
    if city and region:
        return f"{city}, {region}"
    if city:
        return city
    if region and country:
        return f"{region}, {country.upper()}"
    if region:
        return region
    return country.upper() if country else None


def _smartrecruiters_remote_mode(value: object) -> str | None:
    if isinstance(value, dict) and value.get("remote") is True:
        return "remote"
    return None


def _smartrecruiters_description(value: object) -> str | None:
    sections = _smartrecruiters_sections(value)
    parts = [
        _smartrecruiters_section_text(sections.get("companyDescription")),
        _smartrecruiters_section_text(sections.get("jobDescription")),
        _smartrecruiters_section_text(sections.get("additionalInformation")),
    ]
    return " ".join(part for part in parts if part) or None


def _smartrecruiters_qualifications(value: object) -> str | None:
    sections = _smartrecruiters_sections(value)
    return _smartrecruiters_section_text(sections.get("qualifications"))


def _smartrecruiters_sections(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        return {}
    sections = value.get("sections")
    return sections if isinstance(sections, dict) else {}


def _smartrecruiters_section_text(value: object) -> str | None:
    if isinstance(value, dict):
        return _clean_text(value.get("text"))
    return _clean_text(value)


def _workable_location(job: dict[str, Any]) -> str | None:
    locations = job.get("locations")
    if isinstance(locations, list):
        joined = "; ".join(
            location for item in locations if (location := _workable_location_item(item))
        )
        if joined:
            return joined
    return _workable_location_item(job)


def _workable_location_item(value: object) -> str | None:
    if not isinstance(value, dict):
        return _string_or_none(value)
    city = _string_or_none(value.get("city"))
    region = _string_or_none(value.get("state")) or _string_or_none(value.get("region"))
    country = _string_or_none(value.get("country"))
    if city and region:
        return f"{city}, {region}"
    if city and country:
        return f"{city}, {country}"
    if city:
        return city
    if region and country:
        return f"{region}, {country}"
    return region or country


def _workable_remote_mode(job: dict[str, Any]) -> str | None:
    if job.get("telecommuting") is True:
        return "remote"
    return _normalized_workplace_type(job.get("workplace_type"))


def _label_or_text(value: object) -> str | None:
    if isinstance(value, dict):
        return _string_or_none(value.get("label")) or _string_or_none(value.get("name"))
    return _string_or_none(value)


def _first_name(items: object) -> str | None:
    if not isinstance(items, list):
        return None
    for item in items:
        if isinstance(item, dict) and item.get("name"):
            return str(item["name"])
    return None


def _first_location(items: object) -> str | None:
    if not isinstance(items, list):
        return None
    for item in items:
        if isinstance(item, dict):
            location = _string_or_none(item.get("location"))
            if location:
                return location
            name = _string_or_none(item.get("name"))
            if name:
                return name
    return None


def _nested_name(value: object) -> str | None:
    if isinstance(value, dict) and value.get("name"):
        return str(value["name"])
    return None


def _lever_lists_text(value: object) -> str | None:
    if not isinstance(value, list):
        return None
    parts = []
    for item in value:
        if isinstance(item, dict) and item.get("text"):
            parts.append(_clean_text(item["text"]))
    return "\n".join(part for part in parts if part) or None


def _clean_text(value: object) -> str | None:
    if not value:
        return None
    text = html.unescape(str(value))
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def _string_or_none(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _int_or_none(value: object) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None
