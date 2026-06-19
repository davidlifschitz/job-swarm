import json
from pathlib import Path

import pytest

from ml_job_swarm.catalog import (
    infer_source_type,
    import_seed_companies,
    load_seed_companies,
    review_company_source,
    submit_company_source,
)
from ml_job_swarm.adapters import public_ats_registry
from ml_job_swarm.source_policy import classify_source_url
from ml_job_swarm.store import connect, init_db, table_columns


SEED_PATH = Path("data/seed_companies.json")
REQUIRED_TAGS = {
    "ai_lab",
    "ai_infra",
    "big_tech",
    "quant",
    "fintech",
    "developer_tools",
}


def test_seed_catalog_loads_at_least_50_companies():
    companies = load_seed_companies(SEED_PATH)

    assert len(companies) >= 50
    assert REQUIRED_TAGS <= {tag for company in companies for tag in company.tags}


def test_seed_catalog_rejects_names_that_match_normalized_db_key(tmp_path):
    seed_path = tmp_path / "seed_companies.json"
    seed_path.write_text(
        json.dumps(
            [
                {
                    "name": "D.  E. Shaw",
                    "aliases": [],
                    "tags": ["quant"],
                    "stage": "reviewed",
                    "priority_tier": 1,
                    "careers_url": "https://www.deshaw.com/careers",
                    "ats_type": "custom",
                    "reviewed_at": "2026-05-08",
                },
                {
                    "name": "d. e. shaw",
                    "aliases": [],
                    "tags": ["quant"],
                    "stage": "reviewed",
                    "priority_tier": 1,
                    "careers_url": "https://www.deshaw.com/careers",
                    "ats_type": "custom",
                    "reviewed_at": "2026-05-08",
                },
            ]
        )
    )

    with pytest.raises(ValueError, match="duplicate company names"):
        load_seed_companies(seed_path)


def test_seed_company_has_required_fields_and_allowed_source():
    companies = load_seed_companies(SEED_PATH)

    for company in companies:
        assert company.name
        assert isinstance(company.aliases, list)
        assert company.tags
        assert company.stage
        assert company.priority_tier in {1, 2, 3}
        assert company.careers_url.startswith("https://")
        assert company.ats_type
        assert company.reviewed_at == "2026-05-08"
        assert classify_source_url(company.careers_url).mode == "allowed"


def test_seed_catalog_routes_known_generic_careers_pages_away_from_specific_ats():
    companies = {company.name: company for company in load_seed_companies(SEED_PATH)}
    live_failed_generic_pages = {
        "Scale AI",
        "Weights & Biases",
        "Together AI",
        "Anyscale",
        "Replicate",
        "Uber",
        "Two Sigma",
        "Hudson River Trading",
        "Plaid",
        "Coinbase",
        "GitHub",
        "Vercel",
        "Docker",
        "HashiCorp",
        "Sentry",
    }

    for company_name in live_failed_generic_pages:
        company = companies[company_name]
        assert company.ats_type == "careers"


def test_seed_catalog_uses_current_public_careers_urls_for_live_blocked_rows():
    companies = {company.name: company for company in load_seed_companies(SEED_PATH)}

    assert companies["Adept"].careers_url == "https://www.adept.ai/about-careers/"
    assert (
        companies["Citadel Securities"].careers_url
        == "https://www.citadelsecurities.com/careers/"
    )


def test_seed_catalog_primary_sources_use_refreshable_adapters():
    supported_source_types = public_ats_registry().source_types()

    for company in load_seed_companies(SEED_PATH):
        assert company.ats_type in supported_source_types, company.name


def test_seed_catalog_includes_verified_extra_public_sources():
    companies = {company.name: company for company in load_seed_companies(SEED_PATH)}

    expected = {
        "OpenAI": ("https://jobs.ashbyhq.com/openai", "ashby"),
        "Anthropic": ("https://boards.greenhouse.io/anthropic", "greenhouse"),
        "Hugging Face": ("https://apply.workable.com/huggingface/", "workable"),
        "Inflection AI": ("https://boards.greenhouse.io/inflectionai", "greenhouse"),
        "Mistral AI": ("https://jobs.lever.co/mistral", "lever"),
        "Together AI": ("https://boards.greenhouse.io/togetherai", "greenhouse"),
        "Anyscale": ("https://jobs.ashbyhq.com/anyscale", "ashby"),
        "CoreWeave": ("https://boards.greenhouse.io/coreweave", "greenhouse"),
        "Scale AI": ("https://boards.greenhouse.io/scaleai", "greenhouse"),
        "Hudson River Trading": (
            "https://boards.greenhouse.io/hrttalentcommunity",
            "greenhouse",
        ),
    }

    for company_name, source in expected.items():
        company = companies[company_name]
        assert source in [
            (extra_source.url, extra_source.source_type)
            for extra_source in company.extra_sources
        ]


def test_seed_catalog_extra_sources_match_public_provider_type():
    companies = load_seed_companies(SEED_PATH)

    for company in companies:
        for extra_source in company.extra_sources:
            policy = classify_source_url(extra_source.url)
            assert policy.mode == "allowed", company.name
            assert infer_source_type(extra_source.url) == extra_source.source_type


def test_import_seed_companies_adds_extra_reviewed_sources(tmp_path):
    seed_path = tmp_path / "seed_companies.json"
    seed_path.write_text(
        json.dumps(
            [
                {
                    "name": "Example AI",
                    "aliases": [],
                    "tags": ["ai_infra"],
                    "stage": "growth",
                    "priority_tier": 1,
                    "careers_url": "https://example.com/careers",
                    "ats_type": "careers",
                    "extra_sources": [
                        {
                            "url": "https://jobs.ashbyhq.com/example",
                            "source_type": "ashby",
                        }
                    ],
                    "reviewed_at": "2026-05-08",
                }
            ]
        )
    )
    conn = connect()
    init_db(conn)

    first_count = import_seed_companies(conn, seed_path)
    second_count = import_seed_companies(conn, seed_path)

    company = conn.execute(
        "SELECT careers_url, ats_type FROM companies WHERE normalized_name = ?",
        ("example ai",),
    ).fetchone()
    sources = conn.execute(
        "SELECT url, source_type, review_status FROM job_sources ORDER BY url"
    ).fetchall()
    assert first_count == 1
    assert second_count == 0
    assert dict(company) == {
        "careers_url": "https://example.com/careers",
        "ats_type": "careers",
    }
    assert [dict(row) for row in sources] == [
        {
            "url": "https://example.com/careers",
            "source_type": "careers",
            "review_status": "reviewed",
        },
        {
            "url": "https://jobs.ashbyhq.com/example",
            "source_type": "ashby",
            "review_status": "reviewed",
        },
    ]


def test_import_seed_companies_updates_existing_seed_source_metadata(tmp_path):
    seed_path = tmp_path / "seed_companies.json"
    seed_path.write_text(
        json.dumps(
            [
                {
                    "name": "Example AI",
                    "aliases": [],
                    "tags": ["ai_infra"],
                    "stage": "growth",
                    "priority_tier": 1,
                    "careers_url": "https://example.com/careers",
                    "ats_type": "custom",
                    "reviewed_at": "2026-05-08",
                }
            ]
        )
    )
    conn = connect()
    init_db(conn)

    first_count = import_seed_companies(conn, seed_path)
    seed_path.write_text(
        json.dumps(
            [
                {
                    "name": "Example AI",
                    "aliases": ["Example"],
                    "tags": ["ai_lab"],
                    "stage": "enterprise",
                    "priority_tier": 2,
                    "careers_url": "https://example.com/careers",
                    "ats_type": "careers",
                    "reviewed_at": "2026-05-08",
                }
            ]
        )
    )
    second_count = import_seed_companies(conn, seed_path)

    company = conn.execute(
        """
        SELECT aliases_json, categories_json, stage, priority_tier, careers_url, ats_type
        FROM companies
        WHERE normalized_name = ?
        """,
        ("example ai",),
    ).fetchone()
    source = conn.execute(
        "SELECT source_type, policy_mode, review_status FROM job_sources"
    ).fetchone()
    assert first_count == 1
    assert second_count == 0
    assert dict(company) == {
        "aliases_json": '["Example"]',
        "categories_json": '["ai_lab"]',
        "stage": "enterprise",
        "priority_tier": 2,
        "careers_url": "https://example.com/careers",
        "ats_type": "careers",
    }
    assert dict(source) == {
        "source_type": "careers",
        "policy_mode": "allowed",
        "review_status": "reviewed",
    }


def test_import_seed_companies_rejects_blocked_extra_sources(tmp_path):
    seed_path = tmp_path / "seed_companies.json"
    seed_path.write_text(
        json.dumps(
            [
                {
                    "name": "Example AI",
                    "aliases": [],
                    "tags": ["ai_infra"],
                    "stage": "growth",
                    "priority_tier": 1,
                    "careers_url": "https://example.com/careers",
                    "ats_type": "careers",
                    "extra_sources": [
                        {
                            "url": "https://linkedin.com/company/example/jobs",
                            "source_type": "careers",
                        }
                    ],
                    "reviewed_at": "2026-05-08",
                }
            ]
        )
    )
    conn = connect()
    init_db(conn)

    with pytest.raises(ValueError, match="Seed source rejected for Example AI"):
        import_seed_companies(conn, seed_path)
    assert conn.execute("SELECT COUNT(*) FROM companies").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM job_sources").fetchone()[0] == 0


def test_import_seed_companies_is_idempotent():
    conn = connect()
    init_db(conn)

    first_count = import_seed_companies(conn, SEED_PATH)
    second_count = import_seed_companies(conn, SEED_PATH)
    expected_source_count = sum(
        1 + len(company.extra_sources)
        for company in load_seed_companies(SEED_PATH)
    )

    company_count = conn.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
    source_count = conn.execute("SELECT COUNT(*) FROM job_sources").fetchone()[0]
    assert first_count >= 50
    assert second_count == 0
    assert company_count == first_count
    assert source_count == expected_source_count
    assert "priority_tier" in table_columns(conn, "companies")


def test_import_seed_companies_preserves_adapter_source_type(tmp_path):
    seed_path = tmp_path / "seed_companies.json"
    seed_path.write_text(
        json.dumps(
            [
                {
                    "name": "Example AI",
                    "aliases": [],
                    "tags": ["ai_infra"],
                    "stage": "growth",
                    "priority_tier": 1,
                    "careers_url": "https://boards.greenhouse.io/example",
                    "ats_type": "greenhouse",
                    "reviewed_at": "2026-05-08",
                }
            ]
        )
    )
    conn = connect()
    init_db(conn)

    import_seed_companies(conn, seed_path)

    row = conn.execute("SELECT source_type FROM job_sources").fetchone()
    assert row["source_type"] == "greenhouse"


def test_user_added_source_enters_review_queue():
    conn = connect()
    init_db(conn)

    queue_id = submit_company_source(
        conn,
        company_name="New AI Startup",
        source_url="https://newaistartup.example/careers",
    )

    row = conn.execute(
        "SELECT company_name, requested_url, reason, status FROM "
        "company_source_review_queue WHERE id = ?",
        (queue_id,),
    ).fetchone()
    assert dict(row) == {
        "company_name": "New AI Startup",
        "requested_url": "https://newaistartup.example/careers",
        "reason": "manual_review_required",
        "status": "pending",
    }


def test_blocked_user_source_records_policy_result():
    conn = connect()
    init_db(conn)

    queue_id = submit_company_source(
        conn,
        company_name="Bad Source Inc",
        source_url="https://linkedin.com/company/bad-source/jobs",
    )

    row = conn.execute(
        "SELECT reason, status FROM company_source_review_queue WHERE id = ?",
        (queue_id,),
    ).fetchone()
    friction = conn.execute(
        "SELECT event_type, url FROM source_friction_events"
    ).fetchone()

    assert dict(row) == {"reason": "blocked:restricted_source", "status": "blocked"}
    assert dict(friction) == {
        "event_type": "policy_blocked",
        "url": "https://linkedin.com/company/bad-source/jobs",
    }


def test_approve_user_source_creates_reviewed_company_source_and_audit():
    conn = connect()
    init_db(conn)
    queue_id = submit_company_source(
        conn,
        company_name="New AI Startup",
        source_url="https://newaistartup.example/careers",
    )

    result = review_company_source(conn, queue_id, "approve")

    queue = conn.execute(
        """
        SELECT status, reviewed_by, reviewed_at
        FROM company_source_review_queue
        WHERE id = ?
        """,
        (queue_id,),
    ).fetchone()
    source = conn.execute(
        """
        SELECT companies.name, job_sources.url, job_sources.policy_mode,
               job_sources.review_status
        FROM job_sources
        JOIN companies ON companies.id = job_sources.company_id
        """
    ).fetchone()
    audit = conn.execute(
        "SELECT action, target_type, target_id FROM admin_audit_events"
    ).fetchone()

    assert result["status"] == "approved"
    assert queue["status"] == "approved"
    assert queue["reviewed_by"] == "local-admin"
    assert queue["reviewed_at"] is not None
    assert dict(source) == {
        "name": "New AI Startup",
        "url": "https://newaistartup.example/careers",
        "policy_mode": "allowed",
        "review_status": "reviewed",
    }
    assert dict(audit) == {
        "action": "approve",
        "target_type": "company_source_review_queue",
        "target_id": str(queue_id),
    }


def test_reject_user_source_records_review_status_and_audit():
    conn = connect()
    init_db(conn)
    queue_id = submit_company_source(
        conn,
        company_name="New AI Startup",
        source_url="https://newaistartup.example/careers",
    )

    result = review_company_source(conn, queue_id, "reject")

    queue = conn.execute(
        """
        SELECT status, reviewed_by, reviewed_at
        FROM company_source_review_queue
        WHERE id = ?
        """,
        (queue_id,),
    ).fetchone()
    source_count = conn.execute("SELECT COUNT(*) FROM job_sources").fetchone()[0]
    audit = conn.execute(
        "SELECT action, target_type, target_id FROM admin_audit_events"
    ).fetchone()

    assert result["status"] == "rejected"
    assert queue["status"] == "rejected"
    assert queue["reviewed_by"] == "local-admin"
    assert queue["reviewed_at"] is not None
    assert source_count == 0
    assert dict(audit) == {
        "action": "reject",
        "target_type": "company_source_review_queue",
        "target_id": str(queue_id),
    }


def test_blocked_user_source_cannot_be_approved_into_job_sources():
    conn = connect()
    init_db(conn)
    queue_id = submit_company_source(
        conn,
        company_name="Bad Source Inc",
        source_url="https://linkedin.com/company/bad-source/jobs",
    )

    with pytest.raises(ValueError, match="cannot be approved"):
        review_company_source(conn, queue_id, "approve")

    source_count = conn.execute("SELECT COUNT(*) FROM job_sources").fetchone()[0]
    assert source_count == 0


def test_approving_same_user_source_twice_does_not_duplicate_source():
    conn = connect()
    init_db(conn)
    queue_id = submit_company_source(
        conn,
        company_name="New AI Startup",
        source_url="https://newaistartup.example/careers",
    )

    first = review_company_source(conn, queue_id, "approve")
    second = review_company_source(conn, queue_id, "approve")

    company_count = conn.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
    source_count = conn.execute("SELECT COUNT(*) FROM job_sources").fetchone()[0]
    assert first["job_source_id"] == second["job_source_id"]
    assert company_count == 1
    assert source_count == 1


def test_blocked_user_source_can_be_rejected_with_audit():
    conn = connect()
    init_db(conn)
    queue_id = submit_company_source(
        conn,
        company_name="Bad Source Inc",
        source_url="https://linkedin.com/company/bad-source/jobs",
    )

    result = review_company_source(conn, queue_id, "reject")

    queue = conn.execute(
        "SELECT status, reviewed_by, reviewed_at FROM company_source_review_queue"
    ).fetchone()
    source_count = conn.execute("SELECT COUNT(*) FROM job_sources").fetchone()[0]
    audit = conn.execute(
        "SELECT action, target_type, target_id FROM admin_audit_events"
    ).fetchone()
    assert result["status"] == "rejected"
    assert queue["status"] == "rejected"
    assert queue["reviewed_by"] == "local-admin"
    assert queue["reviewed_at"] is not None
    assert source_count == 0
    assert dict(audit) == {
        "action": "reject",
        "target_type": "company_source_review_queue",
        "target_id": str(queue_id),
    }
