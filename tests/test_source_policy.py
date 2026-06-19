from ml_job_swarm.source_policy import classify_source_url


def test_allows_public_ats_urls():
    urls = [
        "https://boards.greenhouse.io/openai",
        "https://boards.greenhouse.io/auth0",
        "https://jobs.lever.co/anthropic",
        "https://jobs.lever.co/sso-company",
        "https://jobs.ashbyhq.com/perplexity",
        "https://jobs.ashbyhq.com/author-labs/jobs/123?ref=author-profile",
        "https://jobs.smartrecruiters.com/Square",
        "https://stripe.com/jobs/search",
        "https://openai.com/careers/search/",
    ]

    for url in urls:
        result = classify_source_url(url)
        assert result.mode == "allowed"
        assert result.normalized_url.startswith("https://")


def test_blocks_linkedin_and_indeed():
    urls = [
        "https://www.linkedin.com/jobs/view/123",
        "https://linkedin.com/company/example/jobs",
        "https://www.indeed.com/viewjob?jk=123",
        "https://indeed.com/jobs?q=machine+learning",
    ]

    for url in urls:
        result = classify_source_url(url)
        assert result.mode == "blocked"
        assert result.normalized_url is None


def test_blocks_auth_or_login_urls():
    urls = [
        "https://example.com/login?next=/careers",
        "https://jobs.example.com/signin",
        "https://example.com/careers?captcha=required",
        "https://example.com/auth/callback",
        "https://boards.greenhouse.io/login",
    ]

    for url in urls:
        result = classify_source_url(url)
        assert result.mode == "blocked"
        assert result.normalized_url is None


def test_blocks_search_result_proxy_urls():
    urls = [
        "https://www.google.com/search?q=site:linkedin.com/jobs+ml",
        "https://www.bing.com/search?q=indeed+machine+learning",
        "https://duckduckgo.com/?q=jobs+at+openai",
    ]

    for url in urls:
        result = classify_source_url(url)
        assert result.mode == "blocked"
        assert result.normalized_url is None


def test_blocks_restricted_source_proxy_urls():
    urls = [
        "https://example.com/careers?target=https://www.linkedin.com/jobs/view/123",
        "https://example.com/jobs?u=https://www.indeed.com/viewjob?jk=123",
    ]

    for url in urls:
        result = classify_source_url(url)
        assert result.mode == "blocked"
        assert result.reason == "restricted_source_proxy"
        assert result.normalized_url is None


def test_google_careers_is_not_treated_as_search_proxy():
    result = classify_source_url(
        "https://www.google.com/about/careers/applications/jobs/results/"
    )

    assert result.mode == "allowed"
    assert result.reason == "public_company_careers"


def test_manual_link_for_unknown_non_company_source():
    result = classify_source_url("https://news.ycombinator.com/item?id=123")

    assert result.mode == "manual_link"
    assert result.normalized_url == "https://news.ycombinator.com/item?id=123"
