import pytest

from ml_job_swarm import adapters
from ml_job_swarm.adapters import (
    AshbyAdapter,
    CareersJsonLdAdapter,
    GreenhouseAdapter,
    LeverAdapter,
    SmartRecruitersAdapter,
    WorkableAdapter,
    WorkdayAdapter,
    public_ats_registry,
)
from ml_job_swarm.ingest import JobSource, RefreshError
from ml_job_swarm.ingest import RawJob


class _CallableFetchOpener:
    def __init__(self, opener_fn):
        self._opener_fn = opener_fn

    def open(self, request, timeout=20):
        return self._opener_fn(request, timeout)


def _patch_default_fetch_opener(monkeypatch, opener_fn):
    monkeypatch.setattr(
        adapters,
        "_build_safe_fetch_opener",
        lambda: _CallableFetchOpener(opener_fn),
    )


def _read_once(self, payload: bytes, _size=-1):
    if getattr(self, "_body_sent", False):
        return b""
    self._body_sent = True
    return payload


def test_greenhouse_adapter_fetches_public_board_jobs():
    seen_urls = []

    def fetch_json(url):
        seen_urls.append(url)
        return {
            "jobs": [
                {
                    "id": 123,
                    "title": "Machine Learning Engineer",
                    "location": {"name": "New York, NY"},
                    "absolute_url": "https://boards.greenhouse.io/example/jobs/123",
                    "content": "<p>Build ML systems.</p>",
                    "departments": [{"name": "Engineering"}],
                }
            ]
        }

    jobs = GreenhouseAdapter(fetch_json=fetch_json).fetch_jobs(
        _source("https://boards.greenhouse.io/example", "greenhouse")
    )

    assert seen_urls == [
        "https://boards-api.greenhouse.io/v1/boards/example/jobs?content=true"
    ]
    assert len(jobs) == 1
    assert jobs[0].external_id == "123"
    assert jobs[0].title == "Machine Learning Engineer"
    assert jobs[0].department == "Engineering"
    assert jobs[0].location_text == "New York, NY"
    assert jobs[0].description_text == "Build ML systems."
    assert jobs[0].source_url == "https://boards.greenhouse.io/example/jobs/123"


@pytest.mark.parametrize(
    ("source_url", "board_token"),
    [
        ("https://www.anthropic.com/careers", "anthropic"),
        ("https://www.databricks.com/company/careers", "databricks"),
        ("https://www.coreweave.com/careers", "coreweave"),
        ("https://careers.airbnb.com/", "airbnb"),
        ("https://www.jumptrading.com/careers/", "jumptrading"),
        ("https://careers.robinhood.com/", "robinhood"),
        ("https://www.brex.com/careers", "brex"),
        ("https://www.affirm.com/careers", "affirm"),
        ("https://www.postman.com/company/careers/", "postman"),
        ("https://about.gitlab.com/jobs/", "gitlab"),
        ("https://x.ai/careers", "xai"),
    ],
)
def test_greenhouse_adapter_derives_board_from_reviewed_careers_host(
    source_url, board_token
):
    seen_urls = []

    def fetch_json(url):
        seen_urls.append(url)
        return {"jobs": []}

    jobs = GreenhouseAdapter(fetch_json=fetch_json).fetch_jobs(
        _source(source_url, "greenhouse")
    )

    assert jobs == []
    assert seen_urls == [
        f"https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true"
    ]


def test_greenhouse_adapter_rejects_generic_non_careers_host_before_fetch():
    def fetch_json(_url):
        raise AssertionError("fetcher should not run for unsupported source URLs")

    adapter = GreenhouseAdapter(fetch_json=fetch_json)

    with pytest.raises(RefreshError):
        adapter.fetch_jobs(_source("https://example.com/about", "greenhouse"))


def test_lever_adapter_fetches_public_postings():
    seen_urls = []

    def fetch_json(url):
        seen_urls.append(url)
        return [
            {
                "id": "posting-1",
                "text": "Research Engineer",
                "categories": {
                    "team": "Research",
                    "location": "Remote US",
                    "commitment": "Full-time",
                },
                "hostedUrl": "https://jobs.lever.co/example/posting-1",
                "descriptionPlain": "Train frontier models.",
                "lists": [{"text": "PyTorch and evaluation."}],
            }
        ]

    jobs = LeverAdapter(fetch_json=fetch_json).fetch_jobs(
        _source("https://jobs.lever.co/example", "lever")
    )

    assert seen_urls == ["https://api.lever.co/v0/postings/example?mode=json"]
    assert len(jobs) == 1
    assert jobs[0].external_id == "posting-1"
    assert jobs[0].title == "Research Engineer"
    assert jobs[0].department == "Research"
    assert jobs[0].location_text == "Remote US"
    assert jobs[0].employment_type == "Full-time"
    assert jobs[0].description_text == "Train frontier models."
    assert jobs[0].requirements_text == "PyTorch and evaluation."


@pytest.mark.parametrize(
    ("source_url", "site"),
    [
        ("https://mistral.ai/careers", "mistral"),
        ("https://careers.example.com/", "example"),
    ],
)
def test_lever_adapter_derives_site_from_reviewed_careers_host(source_url, site):
    seen_urls = []

    def fetch_json(url):
        seen_urls.append(url)
        return []

    jobs = LeverAdapter(fetch_json=fetch_json).fetch_jobs(_source(source_url, "lever"))

    assert jobs == []
    assert seen_urls == [f"https://api.lever.co/v0/postings/{site}?mode=json"]


def test_lever_adapter_rejects_generic_non_careers_host_before_fetch():
    def fetch_json(_url):
        raise AssertionError("fetcher should not run for unsupported source URLs")

    adapter = LeverAdapter(fetch_json=fetch_json)

    with pytest.raises(RefreshError):
        adapter.fetch_jobs(_source("https://example.com/about", "lever"))


def test_ashby_adapter_fetches_public_postings():
    seen_urls = []

    def fetch_json(url):
        seen_urls.append(url)
        return {
            "apiVersion": "1",
            "jobs": [
                {
                    "title": "AI Platform Engineer",
                    "location": "New York, NY",
                    "department": "Engineering",
                    "team": "Infrastructure",
                    "isListed": True,
                    "isRemote": False,
                    "workplaceType": "Hybrid",
                    "descriptionPlain": "Build model-serving systems.",
                    "employmentType": "FullTime",
                    "jobUrl": "https://jobs.ashbyhq.com/example/abc",
                    "applyUrl": "https://jobs.ashbyhq.com/example/abc/application",
                }
            ],
        }

    jobs = AshbyAdapter(fetch_json=fetch_json).fetch_jobs(
        _source("https://jobs.ashbyhq.com/example", "ashby")
    )

    assert seen_urls == [
        "https://api.ashbyhq.com/posting-api/job-board/example?includeCompensation=false"
    ]
    assert len(jobs) == 1
    assert jobs[0].title == "AI Platform Engineer"
    assert jobs[0].department == "Engineering"
    assert jobs[0].location_text == "New York, NY"
    assert jobs[0].remote_mode == "hybrid"
    assert jobs[0].employment_type == "FullTime"
    assert jobs[0].description_text == "Build model-serving systems."
    assert jobs[0].apply_url == "https://jobs.ashbyhq.com/example/abc/application"
    assert jobs[0].source_url == "https://jobs.ashbyhq.com/example/abc"


def test_ashby_adapter_skips_unlisted_postings():
    adapter = AshbyAdapter(
        fetch_json=lambda _url: {
            "jobs": [
                {"title": "Hidden role", "isListed": False},
                {
                    "title": "Listed role",
                    "isListed": True,
                    "jobUrl": "https://jobs.ashbyhq.com/example/listed",
                },
            ]
        }
    )

    jobs = adapter.fetch_jobs(_source("https://jobs.ashbyhq.com/example", "ashby"))

    assert [job.title for job in jobs] == ["Listed role"]


@pytest.mark.parametrize(
    ("adapter", "url"),
    [
        (GreenhouseAdapter(fetch_json=lambda _url: {"jobs": []}), "https://example.com"),
        (LeverAdapter(fetch_json=lambda _url: []), "https://example.com"),
        (AshbyAdapter(fetch_json=lambda _url: {"jobs": []}), "https://example.com"),
    ],
)
def test_public_ats_adapters_reject_unsupported_urls(adapter, url):
    with pytest.raises(RefreshError):
        adapter.fetch_jobs(_source(url, "greenhouse"))


def test_greenhouse_adapter_rejects_malformed_payload():
    adapter = GreenhouseAdapter(fetch_json=lambda _url: {"jobs": {"bad": "payload"}})

    with pytest.raises(RefreshError):
        adapter.fetch_jobs(_source("https://boards.greenhouse.io/example", "greenhouse"))


def test_lever_adapter_rejects_malformed_payload():
    adapter = LeverAdapter(fetch_json=lambda _url: {"bad": "payload"})

    with pytest.raises(RefreshError):
        adapter.fetch_jobs(_source("https://jobs.lever.co/example", "lever"))


def test_ashby_adapter_rejects_malformed_payload():
    adapter = AshbyAdapter(fetch_json=lambda _url: {"jobs": {"bad": "payload"}})

    with pytest.raises(RefreshError):
        adapter.fetch_jobs(_source("https://jobs.ashbyhq.com/example", "ashby"))


def test_workday_adapter_fetches_public_jobs():
    seen_requests = []

    def post_json(url, body):
        seen_requests.append((url, body))
        return {
            "total": 1,
            "jobPostings": [
                {
                    "title": "GPU Systems Software Engineer",
                    "requisitionId": "JR2001234",
                    "externalPath": "/job/US-CA-Santa-Clara/GPU-Systems-Software-Engineer_JR2001234",
                    "locationsText": "US, CA, Santa Clara",
                    "timeType": "Full time",
                    "bulletFields": ["Engineering"],
                }
            ],
        }

    jobs = WorkdayAdapter(post_json=post_json, fetch_json=lambda _url: {}).fetch_jobs(
        _source(
            "https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite",
            "workday",
        )
    )

    assert seen_requests == [
        (
            "https://nvidia.wd5.myworkdayjobs.com/wday/cxs/nvidia/NVIDIAExternalCareerSite/jobs",
            {"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": ""},
        )
    ]
    assert len(jobs) == 1
    assert jobs[0].external_id == "JR2001234"
    assert jobs[0].title == "GPU Systems Software Engineer"
    assert jobs[0].location_text == "US, CA, Santa Clara"
    assert jobs[0].employment_type == "Full time"
    assert jobs[0].source_url == (
        "https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite"
        "/job/US-CA-Santa-Clara/GPU-Systems-Software-Engineer_JR2001234"
    )


def test_workday_adapter_parses_locale_job_urls_to_site():
    seen_requests = []

    def post_json(url, body):
        seen_requests.append((url, body))
        return {"total": 0, "jobPostings": []}

    jobs = WorkdayAdapter(post_json=post_json, fetch_json=lambda _url: {}).fetch_jobs(
        _source(
            "https://nvidia.wd5.myworkdayjobs.com/en-US/NVIDIAExternalCareerSite"
            "/job/US-CA-Santa-Clara/GPU-Systems-Software-Engineer_JR2001234",
            "workday",
        )
    )

    assert jobs == []
    assert seen_requests == [
        (
            "https://nvidia.wd5.myworkdayjobs.com/wday/cxs/nvidia/NVIDIAExternalCareerSite/jobs",
            {"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": ""},
        )
    ]


def test_workday_adapter_hydrates_public_detail_text():
    seen_detail_urls = []

    def post_json(_url, _body):
        return {
            "total": 1,
            "jobPostings": [
                {
                    "title": "GPU Systems Software Engineer",
                    "requisitionId": "JR2001234",
                    "externalPath": "/job/US-CA-Santa-Clara/GPU-Systems-Software-Engineer_JR2001234",
                    "locationsText": "US, CA, Santa Clara",
                    "timeType": "Full time",
                }
            ],
        }

    def fetch_json(url):
        seen_detail_urls.append(url)
        return {
            "jobPostingInfo": {
                "title": "GPU Systems Software Engineer",
                "jobReqId": "JR2001234",
                "jobDescription": "<p>Build distributed GPU compiler systems.</p>",
                "qualifications": "<ul><li>Python and CUDA.</li></ul>",
                "externalUrl": "https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite/job/US-CA-Santa-Clara/GPU-Systems-Software-Engineer_JR2001234",
            }
        }

    jobs = WorkdayAdapter(post_json=post_json, fetch_json=fetch_json).fetch_jobs(
        _source(
            "https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite",
            "workday",
        )
    )

    assert seen_detail_urls == [
        "https://nvidia.wd5.myworkdayjobs.com/wday/cxs/nvidia/NVIDIAExternalCareerSite/job/US-CA-Santa-Clara/GPU-Systems-Software-Engineer_JR2001234"
    ]
    assert len(jobs) == 1
    assert jobs[0].description_text == "Build distributed GPU compiler systems."
    assert jobs[0].requirements_text == "Python and CUDA."
    assert jobs[0].source_url == (
        "https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite"
        "/job/US-CA-Santa-Clara/GPU-Systems-Software-Engineer_JR2001234"
    )


def test_workday_adapter_keeps_list_job_when_detail_fetch_fails():
    def post_json(_url, _body):
        return {
            "total": 1,
            "jobPostings": [
                {
                    "title": "GPU Systems Software Engineer",
                    "requisitionId": "JR2001234",
                    "externalPath": "/job/US-CA-Santa-Clara/GPU-Systems-Software-Engineer_JR2001234",
                    "locationsText": "US, CA, Santa Clara",
                    "timeType": "Full time",
                }
            ],
        }

    def fetch_json(_url):
        raise RefreshError("temporary detail failure", "blocked_response")

    jobs = WorkdayAdapter(post_json=post_json, fetch_json=fetch_json).fetch_jobs(
        _source(
            "https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite",
            "workday",
        )
    )

    assert len(jobs) == 1
    assert jobs[0].title == "GPU Systems Software Engineer"
    assert jobs[0].description_text is None
    assert jobs[0].requirements_text is None


def test_workday_adapter_paginates_public_jobs():
    seen_offsets = []

    def post_json(_url, body):
        seen_offsets.append(body["offset"])
        if body["offset"] == 0:
            return {
                "total": 21,
                "jobPostings": [
                    {
                        "title": f"Role {index}",
                        "externalPath": f"/job/location/role-{index}_JR{index}",
                    }
                    for index in range(20)
                ],
            }
        return {
            "total": 21,
            "jobPostings": [
                {
                    "title": "Role 20",
                    "externalPath": "/job/location/role-20_JR20",
                }
            ],
        }

    jobs = WorkdayAdapter(post_json=post_json, fetch_json=lambda _url: {}).fetch_jobs(
        _source(
            "https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite",
            "workday",
        )
    )

    assert seen_offsets == [0, 20]
    assert len(jobs) == 21
    assert jobs[-1].external_id == "role-20_JR20"


def test_workday_adapter_rejects_malformed_payload():
    adapter = WorkdayAdapter(post_json=lambda _url, _body: {"jobPostings": {}})

    with pytest.raises(RefreshError):
        adapter.fetch_jobs(
            _source(
                "https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite",
                "workday",
            )
        )


def test_workday_adapter_rejects_generic_non_workday_url_before_fetch():
    def post_json(_url, _body):
        raise AssertionError("fetcher should not run for unsupported source URLs")

    adapter = WorkdayAdapter(post_json=post_json)

    with pytest.raises(RefreshError):
        adapter.fetch_jobs(_source("https://www.nvidia.com/en-us/careers", "workday"))


def test_smartrecruiters_adapter_fetches_public_postings_and_details():
    seen_urls = []

    def fetch_json(url):
        seen_urls.append(url)
        if url.endswith("/postings?limit=100&offset=0&destination=PUBLIC"):
            return {
                "totalFound": 1,
                "content": [{"id": "744000123", "name": "ML Engineer"}],
            }
        return {
            "id": "744000123",
            "name": "ML Engineer",
            "department": {"label": "Engineering"},
            "location": {"city": "Oakland", "region": "CA", "country": "us", "remote": True},
            "typeOfEmployment": {"label": "Full-time"},
            "experienceLevel": {"label": "Mid-Senior Level"},
            "applyUrl": "https://jobs.smartrecruiters.com/example/744000123-ml-engineer",
            "postingUrl": "https://jobs.smartrecruiters.com/example/744000123-ml-engineer",
            "jobAd": {
                "sections": {
                    "companyDescription": {"text": "Build useful systems."},
                    "jobDescription": {"text": "Train ranking models."},
                    "qualifications": {"text": "Python and ML."},
                }
            },
        }

    jobs = SmartRecruitersAdapter(fetch_json=fetch_json).fetch_jobs(
        _source("https://jobs.smartrecruiters.com/example", "smartrecruiters")
    )

    assert seen_urls == [
        "https://api.smartrecruiters.com/v1/companies/example/postings?limit=100&offset=0&destination=PUBLIC",
        "https://api.smartrecruiters.com/v1/companies/example/postings/744000123",
    ]
    assert len(jobs) == 1
    assert jobs[0].external_id == "744000123"
    assert jobs[0].title == "ML Engineer"
    assert jobs[0].department == "Engineering"
    assert jobs[0].location_text == "Oakland, CA"
    assert jobs[0].remote_mode == "remote"
    assert jobs[0].employment_type == "Full-time"
    assert jobs[0].seniority == "Mid-Senior Level"
    assert jobs[0].description_text == "Build useful systems. Train ranking models."
    assert jobs[0].requirements_text == "Python and ML."
    assert jobs[0].apply_url == "https://jobs.smartrecruiters.com/example/744000123-ml-engineer"


def test_smartrecruiters_adapter_accepts_api_source_url():
    seen_urls = []

    def fetch_json(url):
        seen_urls.append(url)
        return {"totalFound": 0, "content": []}

    jobs = SmartRecruitersAdapter(fetch_json=fetch_json).fetch_jobs(
        _source(
            "https://api.smartrecruiters.com/v1/companies/example/postings",
            "smartrecruiters",
        )
    )

    assert jobs == []
    assert seen_urls == [
        "https://api.smartrecruiters.com/v1/companies/example/postings?limit=100&offset=0&destination=PUBLIC"
    ]


def test_smartrecruiters_adapter_paginates_public_postings():
    seen_urls = []

    def fetch_json(url):
        seen_urls.append(url)
        if "offset=0" in url:
            return {
                "totalFound": 101,
                "content": [{"id": str(index), "name": f"Role {index}"} for index in range(100)],
            }
        if "offset=100" in url:
            return {
                "totalFound": 101,
                "content": [{"id": "100", "name": "Role 100"}],
            }
        posting_id = url.rsplit("/", 1)[-1]
        return {"id": posting_id, "name": f"Role {posting_id}"}

    jobs = SmartRecruitersAdapter(fetch_json=fetch_json).fetch_jobs(
        _source("https://careers.smartrecruiters.com/example", "smartrecruiters")
    )

    assert (
        "https://api.smartrecruiters.com/v1/companies/example/postings?limit=100&offset=100&destination=PUBLIC"
        in seen_urls
    )
    assert len(jobs) == 101
    assert jobs[-1].external_id == "100"


def test_smartrecruiters_adapter_rejects_malformed_payload():
    adapter = SmartRecruitersAdapter(fetch_json=lambda _url: {"content": {}})

    with pytest.raises(RefreshError):
        adapter.fetch_jobs(
            _source("https://jobs.smartrecruiters.com/example", "smartrecruiters")
        )


def test_smartrecruiters_adapter_rejects_generic_non_smartrecruiters_url():
    def fetch_json(_url):
        raise AssertionError("fetcher should not run for unsupported source URLs")

    adapter = SmartRecruitersAdapter(fetch_json=fetch_json)

    with pytest.raises(RefreshError):
        adapter.fetch_jobs(_source("https://block.xyz/careers", "smartrecruiters"))


def test_workable_adapter_fetches_public_jobs():
    seen_urls = []

    def fetch_json(url):
        seen_urls.append(url)
        return {
            "name": "Example AI",
            "description": "Example jobs",
            "jobs": [
                {
                    "title": "Machine Learning Engineer",
                    "shortcode": "ABC123",
                    "code": "ML-1",
                    "department": "Engineering",
                    "city": "New York",
                    "state": "NY",
                    "country": "United States",
                    "telecommuting": True,
                    "employment_type": "Full-time",
                    "experience": "Mid-Senior level",
                    "description": "<p>Build model serving systems.</p>",
                    "url": "https://apply.workable.com/j/ABC123",
                    "application_url": "https://apply.workable.com/j/ABC123/apply",
                }
            ],
        }

    jobs = WorkableAdapter(fetch_json=fetch_json).fetch_jobs(
        _source("https://apply.workable.com/example-ai/", "workable")
    )

    assert seen_urls == [
        "https://www.workable.com/api/accounts/example-ai?details=true"
    ]
    assert len(jobs) == 1
    assert jobs[0].external_id == "ABC123"
    assert jobs[0].title == "Machine Learning Engineer"
    assert jobs[0].department == "Engineering"
    assert jobs[0].location_text == "New York, NY"
    assert jobs[0].remote_mode == "remote"
    assert jobs[0].employment_type == "Full-time"
    assert jobs[0].seniority == "Mid-Senior level"
    assert jobs[0].description_text == "Build model serving systems."
    assert jobs[0].apply_url == "https://apply.workable.com/j/ABC123/apply"
    assert jobs[0].source_url == "https://apply.workable.com/j/ABC123"


def test_workable_adapter_accepts_public_api_source_url():
    seen_urls = []

    def fetch_json(url):
        seen_urls.append(url)
        return {"jobs": []}

    jobs = WorkableAdapter(fetch_json=fetch_json).fetch_jobs(
        _source("https://www.workable.com/api/accounts/example-ai", "workable")
    )

    assert jobs == []
    assert seen_urls == [
        "https://www.workable.com/api/accounts/example-ai?details=true"
    ]


def test_workable_adapter_rejects_job_shortlink_without_account_before_fetch():
    def fetch_json(_url):
        raise AssertionError("fetcher should not run for unsupported source URLs")

    adapter = WorkableAdapter(fetch_json=fetch_json)

    with pytest.raises(RefreshError):
        adapter.fetch_jobs(_source("https://apply.workable.com/j/ABC123", "workable"))


def test_workable_adapter_rejects_malformed_payload():
    adapter = WorkableAdapter(fetch_json=lambda _url: {"jobs": {"bad": "payload"}})

    with pytest.raises(RefreshError):
        adapter.fetch_jobs(_source("https://apply.workable.com/example-ai/", "workable"))


def test_careers_jsonld_adapter_extracts_public_jobposting():
    seen_urls = []

    def fetch_text(url):
        seen_urls.append(url)
        return """
        <html>
          <head>
            <script type="application/ld+json">
            {
              "@context": "https://schema.org",
              "@type": "JobPosting",
              "title": "Machine Learning Engineer",
              "description": "<p>Build ranking systems.</p>",
              "employmentType": "FULL_TIME",
              "jobLocationType": "TELECOMMUTE",
              "jobLocation": {
                "@type": "Place",
                "address": {
                  "addressLocality": "New York",
                  "addressRegion": "NY",
                  "addressCountry": "US"
                }
              },
              "qualifications": "Python and PyTorch.",
              "url": "https://example.com/careers/ml-engineer",
              "identifier": {"value": "ml-engineer"}
            }
            </script>
          </head>
        </html>
        """

    jobs = CareersJsonLdAdapter(fetch_text=fetch_text).fetch_jobs(
        _source("https://example.com/careers", "careers")
    )

    assert seen_urls == ["https://example.com/careers"]
    assert len(jobs) == 1
    assert jobs[0].external_id == "ml-engineer"
    assert jobs[0].title == "Machine Learning Engineer"
    assert jobs[0].location_text == "New York, NY, US"
    assert jobs[0].remote_mode == "remote"
    assert jobs[0].employment_type == "FULL_TIME"
    assert jobs[0].description_text == "Build ranking systems."
    assert jobs[0].requirements_text == "Python and PyTorch."
    assert jobs[0].apply_url == "https://example.com/careers/ml-engineer"


def test_careers_jsonld_adapter_handles_graph_payloads_and_ignores_non_jobs():
    adapter = CareersJsonLdAdapter(
        fetch_text=lambda _url: """
        <script type="application/ld+json">
        {
          "@graph": [
            {"@type": "Organization", "name": "Example AI"},
            {
              "@type": ["Thing", "JobPosting"],
              "title": "AI Platform Engineer",
              "description": "Operate model serving.",
              "jobLocation": {"name": "Remote US"},
              "url": "https://example.com/jobs/platform"
            }
          ]
        }
        </script>
        """
    )

    jobs = adapter.fetch_jobs(_source("https://example.com/jobs", "careers"))

    assert [job.title for job in jobs] == ["AI Platform Engineer"]
    assert jobs[0].location_text == "Remote US"
    assert jobs[0].source_url == "https://example.com/jobs/platform"


def test_careers_jsonld_adapter_returns_empty_for_pages_without_jobposting():
    adapter = CareersJsonLdAdapter(
        fetch_text=lambda _url: """
        <script type="application/ld+json">
        {"@type": "Organization", "name": "Example AI"}
        </script>
        """
    )

    assert adapter.fetch_jobs(_source("https://example.com/careers", "careers")) == []


def test_careers_jsonld_adapter_extracts_same_domain_public_job_links():
    adapter = CareersJsonLdAdapter(
        fetch_text=lambda _url: """
        <a href="/about">About us</a>
        <a href="/careers">Open Positions</a>
        <a href="/careers/software-engineer-ai">Software Engineer, AI Read more</a>
        <a href="https://example.com/jobs/data-platform-engineer">
          Data Platform Engineer
        </a>
        <a href="https://other.example/jobs/not-ours">Other Company Engineer</a>
        <a href="mailto:jobs@example.com">Email us</a>
        """
    )

    jobs = adapter.fetch_jobs(_source("https://example.com/careers", "careers"))

    assert [(job.title, job.apply_url) for job in jobs] == [
        ("Software Engineer, AI", "https://example.com/careers/software-engineer-ai"),
        ("Data Platform Engineer", "https://example.com/jobs/data-platform-engineer"),
    ]
    assert [job.external_id for job in jobs] == [
        "careers/software-engineer-ai",
        "jobs/data-platform-engineer",
    ]


def test_careers_jsonld_adapter_ignores_same_domain_index_facets():
    adapter = CareersJsonLdAdapter(
        fetch_text=lambda _url: """
        <a href="/careers-home/jobs/locations/bellevue">Bellevue</a>
        <a href="/careers-home/jobs/categories/engineering">Engineering</a>
        <a href="/careers-home/jobs/{{assessmentUrl}}">{{assessmentUrl}}</a>
        <a href="/careers/list">Español (Internacional)</a>
        <a href="/careers/software-engineer-ai">Software Engineer, AI</a>
        """
    )

    jobs = adapter.fetch_jobs(_source("https://example.com/careers", "careers"))

    assert [(job.title, job.apply_url) for job in jobs] == [
        ("Software Engineer, AI", "https://example.com/careers/software-engineer-ai")
    ]


def test_careers_jsonld_adapter_delegates_embedded_provider_urls_in_scripts():
    greenhouse = _FakeProviderAdapter("Greenhouse Role")
    adapter = CareersJsonLdAdapter(
        fetch_text=lambda _url: """
        <script>
          window.__BOARD__ = "https://boards.greenhouse.io/example";
          const ashby = "https://jobs.ashbyhq.com/example";
        </script>
        """,
        provider_adapters={"greenhouse": greenhouse, "ashby": _FakeProviderAdapter("Ashby Role")},
    )

    jobs = adapter.fetch_jobs(_source("https://example.com/careers", "careers"))

    assert [job.title for job in jobs] == ["Greenhouse Role", "Ashby Role"]
    assert greenhouse.calls[0].url == "https://boards.greenhouse.io/example"


def test_careers_jsonld_adapter_delegates_public_provider_links():
    greenhouse = _FakeProviderAdapter("Greenhouse Role")
    ashby = _FakeProviderAdapter("Ashby Role")
    adapter = CareersJsonLdAdapter(
        fetch_text=lambda _url: """
        <a href="/about">About</a>
        <a href="https://boards.greenhouse.io/example">Open roles</a>
        <a href="https://jobs.ashbyhq.com/example">More roles</a>
        """,
        provider_adapters={"greenhouse": greenhouse, "ashby": ashby},
    )

    jobs = adapter.fetch_jobs(_source("https://example.com/careers", "careers"))

    assert [job.title for job in jobs] == ["Greenhouse Role", "Ashby Role"]
    assert [(source.url, source.source_type) for source in greenhouse.calls] == [
        ("https://boards.greenhouse.io/example", "greenhouse")
    ]
    assert [(source.url, source.source_type) for source in ashby.calls] == [
        ("https://jobs.ashbyhq.com/example", "ashby")
    ]


def test_careers_jsonld_adapter_dedupes_provider_board_filter_links():
    lever = _FakeProviderAdapter("Lever Role")
    ashby = _FakeProviderAdapter("Ashby Role")
    adapter = CareersJsonLdAdapter(
        fetch_text=lambda _url: """
        <a href="https://jobs.lever.co/mistral?team=Research">Research</a>
        <a href="https://jobs.lever.co/mistral?team=Engineering">Engineering</a>
        <a href="https://jobs.ashbyhq.com/anyscale?departmentId=1">Infra</a>
        <a href="https://jobs.ashbyhq.com/anyscale?departmentId=2">Research</a>
        """,
        provider_adapters={"lever": lever, "ashby": ashby},
    )

    jobs = adapter.fetch_jobs(_source("https://example.com/careers", "careers"))

    assert [job.title for job in jobs] == ["Lever Role", "Ashby Role"]
    assert [(source.url, source.source_type) for source in lever.calls] == [
        ("https://jobs.lever.co/mistral", "lever")
    ]
    assert [(source.url, source.source_type) for source in ashby.calls] == [
        ("https://jobs.ashbyhq.com/anyscale", "ashby")
    ]


def test_careers_jsonld_adapter_ignores_restricted_auth_and_search_links():
    adapter = CareersJsonLdAdapter(
        fetch_text=lambda _url: """
        <a href="https://www.linkedin.com/jobs/search/?keywords=ML">LinkedIn</a>
        <a href="https://www.indeed.com/jobs?q=machine+learning">Indeed</a>
        <a href="https://www.google.com/search?q=site:jobs.lever.co/example">Search</a>
        <a href="https://jobs.lever.co/example/login">Login</a>
        <a href="https://jobs.ashbyhq.com/example/captcha">Captcha</a>
        <a href="mailto:jobs@example.com">Email</a>
        """,
        provider_adapters={
            "lever": _FailingProviderAdapter(),
            "ashby": _FailingProviderAdapter(),
        },
    )

    assert adapter.fetch_jobs(_source("https://example.com/careers", "careers")) == []


def test_careers_jsonld_adapter_ignores_generic_provider_marketing_links():
    adapter = CareersJsonLdAdapter(
        fetch_text=lambda _url: """
        <a href="https://boards.greenhouse.io/job-boards">Powered by Greenhouse</a>
        """,
        provider_adapters={"greenhouse": _FailingProviderAdapter()},
    )

    assert adapter.fetch_jobs(_source("https://example.com/careers", "careers")) == []


def test_careers_jsonld_adapter_rejects_generic_non_careers_url_before_fetch():
    def fetch_text(_url):
        raise AssertionError("fetcher should not run for unsupported source URLs")

    adapter = CareersJsonLdAdapter(fetch_text=fetch_text)

    with pytest.raises(RefreshError):
        adapter.fetch_jobs(_source("https://example.com/about", "careers"))


@pytest.mark.parametrize(
    "source_url",
    [
        "https://www.amazon.jobs/",
        "https://github.careers/",
        "https://www.adept.ai/about-careers/",
        "https://www.tower-research.com/open-positions/",
        "https://optiver.com/working-at-optiver/career-opportunities/",
    ],
)
def test_careers_jsonld_adapter_accepts_common_public_career_url_shapes(source_url):
    adapter = CareersJsonLdAdapter(
        fetch_text=lambda _url: """
        <script type="application/ld+json">
        {
          "@type": "JobPosting",
          "title": "Research Engineer",
          "url": "https://example.com/jobs/research-engineer"
        }
        </script>
        """
    )

    jobs = adapter.fetch_jobs(_source(source_url, "careers"))

    assert [job.title for job in jobs] == ["Research Engineer"]


def test_public_ats_registry_includes_supported_source_types():
    assert {
        "greenhouse",
        "lever",
        "ashby",
        "careers",
        "workday",
        "smartrecruiters",
        "workable",
    } <= public_ats_registry().source_types()


def test_seed_company_specific_ats_urls_match_registered_adapter_shapes():
    import json
    from pathlib import Path
    from urllib.parse import urlsplit

    seed_companies = json.loads(Path("data/seed_companies.json").read_text())

    for company in seed_companies:
        source_type = company.get("ats_type")
        host = (urlsplit(company["careers_url"]).hostname or "").lower()
        if source_type == "workday":
            assert host.endswith("myworkdayjobs.com"), company["name"]
        if source_type == "smartrecruiters":
            assert host.endswith("smartrecruiters.com"), company["name"]


def test_default_public_ats_fetcher_sends_browser_compatible_headers(monkeypatch):
    seen_requests = []

    class FakeHeaders:
        def get_content_charset(self):
            return "utf-8"

    class FakeResponse:
        headers = FakeHeaders()

        def __enter__(self):
            return self

        def __exit__(self, _exc_type, _exc, _tb):
            return False

        def read(self, _size=-1):
            return _read_once(self, b'{"jobs": []}')

    def fake_urlopen(request, timeout):
        seen_requests.append((request, timeout))
        return FakeResponse()

    monkeypatch.setattr(adapters, "_build_safe_fetch_opener", lambda: _CallableFetchOpener(fake_urlopen))

    assert adapters._default_fetch_json("https://api.ashbyhq.com/posting-api/job-board/openai") == {
        "jobs": []
    }

    [(request, timeout)] = seen_requests
    assert timeout == 20
    assert request.get_header("Accept") == "application/json"
    assert request.get_header("User-agent").startswith("Mozilla/5.0")


def test_default_public_ats_fetcher_retries_transient_timeout(monkeypatch):
    seen_requests = []

    class FakeHeaders:
        def get_content_charset(self):
            return "utf-8"

    class FakeResponse:
        def __init__(self, should_timeout=False):
            self._should_timeout = should_timeout

        headers = FakeHeaders()

        def __enter__(self):
            return self

        def __exit__(self, _exc_type, _exc, _tb):
            return False

        def read(self, _size=-1):
            if self._should_timeout:
                raise TimeoutError("read operation timed out")
            return _read_once(self, b'{"jobs": []}')

    def fake_urlopen(request, timeout):
        seen_requests.append((request, timeout))
        if len(seen_requests) == 1:
            return FakeResponse(should_timeout=True)
        return FakeResponse()

    monkeypatch.setattr(adapters, "_build_safe_fetch_opener", lambda: _CallableFetchOpener(fake_urlopen))

    assert adapters._default_fetch_json("https://api.ashbyhq.com/posting-api/job-board/openai") == {
        "jobs": []
    }
    assert len(seen_requests) == 2


def test_default_public_careers_fetcher_retries_transient_timeout(monkeypatch):
    seen_requests = []

    class FakeHeaders:
        def get_content_charset(self):
            return "utf-8"

    class FakeResponse:
        headers = FakeHeaders()

        def __enter__(self):
            return self

        def __exit__(self, _exc_type, _exc, _tb):
            return False

        def read(self, _size=-1):
            return _read_once(self, b"<html></html>")

    def fake_urlopen(request, timeout):
        seen_requests.append((request, timeout))
        if len(seen_requests) == 1:
            raise TimeoutError("timed out")
        return FakeResponse()

    monkeypatch.setattr(adapters, "_build_safe_fetch_opener", lambda: _CallableFetchOpener(fake_urlopen))

    assert adapters._default_fetch_text("https://github.careers/") == "<html></html>"
    assert len(seen_requests) == 2


def test_default_public_careers_fetcher_reports_persistent_timeout(monkeypatch):
    def fake_urlopen(_request, timeout):
        raise TimeoutError("timed out")

    monkeypatch.setattr(adapters, "_build_safe_fetch_opener", lambda: _CallableFetchOpener(fake_urlopen))

    with pytest.raises(RefreshError) as exc_info:
        adapters._default_fetch_text("https://careers.example.com/")

    assert exc_info.value.event_type == "timeout"


def test_default_public_careers_fetcher_preserves_http_status_code(monkeypatch):
    def fake_urlopen(request, timeout):
        raise adapters.HTTPError(
            request.full_url,
            403,
            "Forbidden",
            hdrs=None,
            fp=None,
        )

    monkeypatch.setattr(adapters, "_build_safe_fetch_opener", lambda: _CallableFetchOpener(fake_urlopen))

    with pytest.raises(RefreshError) as exc_info:
        adapters._default_fetch_text("https://www.citadelsecurities.com/careers/")

    assert exc_info.value.event_type == "blocked_response"
    assert exc_info.value.status_code == 403


def test_default_public_fetchers_classify_http_429_as_rate_limited(monkeypatch):
    def fake_urlopen(request, timeout):
        raise adapters.HTTPError(
            request.full_url,
            429,
            "Too Many Requests",
            hdrs=None,
            fp=None,
        )

    monkeypatch.setattr(adapters, "_build_safe_fetch_opener", lambda: _CallableFetchOpener(fake_urlopen))

    with pytest.raises(RefreshError) as json_exc:
        adapters._default_fetch_json("https://boards-api.greenhouse.io/v1/boards/example/jobs")
    with pytest.raises(RefreshError) as text_exc:
        adapters._default_fetch_text("https://example.com/careers")
    with pytest.raises(RefreshError) as post_exc:
        adapters._default_post_json(
            "https://example.myworkdayjobs.com/wday/cxs/example/site/jobs",
            {"limit": 20},
        )

    for exc_info in (json_exc, text_exc, post_exc):
        assert exc_info.value.event_type == "rate_limited"
        assert exc_info.value.status_code == 429


def test_default_public_ats_fetcher_reports_persistent_timeout(monkeypatch):
    def fake_urlopen(_request, timeout):
        raise TimeoutError("timed out")

    monkeypatch.setattr(adapters, "_build_safe_fetch_opener", lambda: _CallableFetchOpener(fake_urlopen))

    with pytest.raises(RefreshError) as exc_info:
        adapters._default_fetch_json("https://api.ashbyhq.com/posting-api/job-board/openai")

    assert exc_info.value.event_type == "timeout"


def test_default_public_ats_post_fetcher_retries_transient_timeout(monkeypatch):
    seen_requests = []

    class FakeHeaders:
        def get_content_charset(self):
            return "utf-8"

    class FakeResponse:
        headers = FakeHeaders()

        def __enter__(self):
            return self

        def __exit__(self, _exc_type, _exc, _tb):
            return False

        def read(self, _size=-1):
            return _read_once(self, b'{"jobPostings": []}')

    def fake_urlopen(request, timeout):
        seen_requests.append((request, timeout))
        if len(seen_requests) == 1:
            raise TimeoutError("timed out")
        return FakeResponse()

    monkeypatch.setattr(adapters, "_build_safe_fetch_opener", lambda: _CallableFetchOpener(fake_urlopen))

    assert adapters._default_post_json(
        "https://example.myworkdayjobs.com/wday/cxs/example/site/jobs",
        {"limit": 20},
    ) == {"jobPostings": []}
    assert len(seen_requests) == 2


def _source(url, source_type):
    return JobSource(
        id=1,
        company_id=1,
        url=url,
        source_type=source_type,
        policy_mode="allowed",
        review_status="reviewed",
    )


class _FakeProviderAdapter:
    def __init__(self, title):
        self.title = title
        self.calls = []

    def fetch_jobs(self, source):
        self.calls.append(source)
        return [
            RawJob(
                external_id=self.title.casefold().replace(" ", "-"),
                title=self.title,
                source_url=source.url,
                apply_url=source.url,
            )
        ]


class _FailingProviderAdapter:
    def fetch_jobs(self, _source):
        raise AssertionError("provider adapter should not run")
