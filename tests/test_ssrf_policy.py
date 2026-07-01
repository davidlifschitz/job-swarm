import pytest

from ml_job_swarm.source_policy import classify_source_url


@pytest.mark.parametrize(
    "url",
    [
        "https://127.0.0.1/careers",
        "https://localhost/jobs",
        "http://169.254.169.254/latest/meta-data/",
        "https://10.0.0.12/careers",
        "https://192.168.1.50/jobs",
        "https://[::1]/jobs",
        "https://[::]/admin",
    ],
)
def test_blocks_private_or_reserved_hosts(url):
    result = classify_source_url(url)
    assert result.mode == "blocked"
    assert result.reason == "private_or_reserved_host"
    assert result.normalized_url is None
