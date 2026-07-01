from __future__ import annotations

import io
from urllib.request import Request

import pytest

from ml_job_swarm.adapters import (
    MAX_FETCH_RESPONSE_BYTES,
    _SafeRedirectHandler,
    _read_url_request,
)
from ml_job_swarm.ingest import RefreshError
from ml_job_swarm.source_policy import assert_safe_fetch_url


@pytest.mark.parametrize(
    "url",
    [
        "https://127.0.0.1/careers",
        "http://[::1]/jobs",
        "http://[::]/admin",
        "https://169.254.169.254/latest/meta-data/",
    ],
)
def test_assert_safe_fetch_url_blocks_private_or_unspecified_hosts(url):
    with pytest.raises(ValueError, match="blocked fetch host"):
        assert_safe_fetch_url(url)


def test_assert_safe_fetch_url_allows_public_https_urls():
    assert (
        assert_safe_fetch_url("https://boards.greenhouse.io/example/jobs.json")
        == "https://boards.greenhouse.io/example/jobs.json"
    )


def test_safe_redirect_handler_blocks_private_target():
    handler = _SafeRedirectHandler()
    request = Request("https://boards.greenhouse.io/example/jobs.json")

    with pytest.raises(ValueError, match="blocked fetch host"):
        handler.redirect_request(
            request,
            None,
            302,
            "Found",
            {},
            "http://127.0.0.1/private",
        )


def test_read_url_request_rejects_oversized_response(monkeypatch):
    class LargeResponse:
        headers = type("Headers", (), {"get_content_charset": lambda self: "utf-8"})()

        def read(self, size=-1):
            return b"x" * (1024 * 1024)

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    class LargeOpener:
        def open(self, request, timeout=20):
            return LargeResponse()

    monkeypatch.setattr("ml_job_swarm.adapters._build_safe_fetch_opener", lambda: LargeOpener())

    with pytest.raises(RefreshError, match="too large"):
        _read_url_request(Request("https://boards.greenhouse.io/example/jobs.json"))

    assert MAX_FETCH_RESPONSE_BYTES == 5 * 1024 * 1024
