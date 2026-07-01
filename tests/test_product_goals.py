from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from ml_job_swarm.product_goals import (
    PRODUCT_SOURCE_STATUSES,
    audit_seed_sources,
    build_live_smoke_product_metrics,
    catalog_quality_metrics,
    evaluate_product_metrics,
    local_referral_alias_match_report,
    manual_submit_boundary_report,
    next_action_coverage,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_seed_sources_have_explicit_policy_classification():
    seed_companies = json.loads((REPO_ROOT / "data" / "seed_companies.json").read_text())
    mixed_sources = [
        {
            "name": "Allowed ATS",
            "careers_url": "https://jobs.lever.co/example",
            "ats_type": "lever",
        },
        {
            "name": "Unsupported Public Source",
            "careers_url": "https://example.com/careers",
            "ats_type": "custom",
        },
        {
            "name": "Blocked Source",
            "careers_url": "https://www.linkedin.com/jobs/view/123",
            "ats_type": "careers",
        },
        {
            "name": "Needs Review Source",
            "careers_url": "https://news.ycombinator.com/item?id=123",
            "ats_type": "careers",
        },
    ]

    seeded_records = audit_seed_sources(seed_companies)
    mixed_records = audit_seed_sources(mixed_sources)

    assert seeded_records
    assert all(record.status in PRODUCT_SOURCE_STATUSES for record in seeded_records)
    assert all(record.next_action for record in seeded_records)
    assert {record.status for record in mixed_records} == {
        "supported",
        "unsupported",
        "blocked",
        "needs_review",
    }


def test_evaluate_product_metrics_passes_on_good_live_smoke_metrics():
    metrics = build_live_smoke_product_metrics(
        refresh_summary={
            "jobs_seen": 422,
            "sources_attempted": 10,
            "sources_succeeded": 10,
        },
        packet_prepared=True,
        saved_jobs_count=1,
        elapsed_seconds=45.0,
    )

    assert evaluate_product_metrics(metrics) == []


def test_evaluate_product_metrics_reports_violations_on_bad_metrics():
    violations = evaluate_product_metrics(
        {
            "first_run": {
                "browser_e2e_ok": False,
                "elapsed_seconds": 120.0,
                "target_seconds": 600,
            },
            "source_refresh": {
                "supported_source_success_rate": 0.5,
                "target_success_rate": 0.9,
            },
            "catalog": {
                "jobs_seen": 0,
                "target_jobs_seen_min": 1,
            },
            "application_packets": {
                "prepared_packet_rate": 0.5,
                "target_prepared_packet_rate": 0.95,
            },
            "manual_submission": {
                "external_submit_paths": 2,
                "target_external_submit_paths": 0,
            },
        }
    )

    assert len(violations) == 5
    assert any("success rate" in violation.casefold() for violation in violations)
    assert any("prepared packet rate" in violation.casefold() for violation in violations)
    assert any("external submit path" in violation.casefold() for violation in violations)
    assert any("jobs_seen" in violation for violation in violations)
    assert any("browser e2e" in violation.casefold() for violation in violations)


def test_live_smoke_reports_quantitative_product_metrics():
    metrics = build_live_smoke_product_metrics(
        refresh_summary={
            "jobs_seen": 422,
            "sources_attempted": 1,
            "sources_succeeded": 1,
        },
        packet_prepared=True,
        saved_jobs_count=1,
        elapsed_seconds=45.0,
    )

    assert metrics["first_run"]["browser_e2e_ok"] is True
    assert metrics["first_run"]["target_seconds"] == 600
    assert metrics["source_refresh"]["supported_source_success_rate"] == 1.0
    assert metrics["source_refresh"]["target_success_rate"] == 0.9
    assert metrics["catalog"]["jobs_seen"] == 422
    assert metrics["application_packets"]["prepared_packet_rate"] == 1.0
    assert metrics["manual_submission"]["external_submit_paths"] == 0


def test_live_smoke_marks_unexplained_source_failures_not_visible():
    metrics = build_live_smoke_product_metrics(
        refresh_summary={
            "jobs_seen": 0,
            "sources_attempted": 2,
            "sources_succeeded": 1,
        },
        packet_prepared=False,
        saved_jobs_count=0,
        source_failures=[],
    )

    assert metrics["source_refresh"]["sources_have_visible_failure_reasons"] is False
    assert metrics["source_refresh"]["missing_failure_reason_count"] == 1


def test_dashboard_renders_next_action_for_each_empty_or_failed_state():
    report = next_action_coverage(
        [
            {"state": "no_resume", "next_action": "Upload resume"},
            {"state": "no_profile", "next_action": "Create target profile"},
            {"state": "source_failed", "next_action": "Open source health"},
            {"state": "no_saved_jobs", "next_action": "Save a matching job"},
        ]
    )

    assert report["coverage_rate"] == 1.0
    assert report["missing_states"] == []


def test_application_packet_requires_manual_submit_boundary(tmp_path):
    source_root = tmp_path / "source"
    source_root.mkdir()
    (source_root / "safe.py").write_text(
        "def prepare_packet():\n"
        "    return {'status': 'prepared', 'manual_submit_url': 'https://example.com/jobs'}\n"
    )
    (source_root / "unsafe.py").write_text("def submit_application():\n    pass\n")

    unsafe_report = manual_submit_boundary_report(source_root)
    repo_report = manual_submit_boundary_report(REPO_ROOT / "ml_job_swarm")

    assert unsafe_report["external_submit_paths"] == ["unsafe.py"]
    assert repo_report["external_submit_paths"] == []
    assert repo_report["manual_statuses"] == ["prepared", "submitted"]


def test_local_referrals_match_company_aliases_without_outreach():
    report = local_referral_alias_match_report(
        companies=[
            {"id": 1, "name": "Google DeepMind", "aliases": ["DeepMind"]},
            {"id": 2, "name": "Anthropic", "aliases": []},
        ],
        contacts=[
            {"company_id": 1, "name": "Dana"},
            {"company_id": 2, "name": "Riley"},
        ],
        jobs=[
            {"id": 10, "company_name": "DeepMind", "expected_company_id": 1},
            {"id": 11, "company_name": "Anthropic", "expected_company_id": 2},
        ],
    )

    assert report["precision"] == 1.0
    assert report["suggestions"] == [
        {"job_id": 10, "company_id": 1, "contact_count": 1},
        {"job_id": 11, "company_id": 2, "contact_count": 1},
    ]
    assert report["outbound_action_count"] == 0


def test_local_referral_precision_does_not_count_unlabeled_jobs_as_true_positive():
    report = local_referral_alias_match_report(
        companies=[{"id": 1, "name": "Google DeepMind", "aliases": ["DeepMind"]}],
        contacts=[{"company_id": 1, "name": "Dana"}],
        jobs=[{"id": 10, "company_name": "DeepMind"}],
    )

    assert report["precision"] is None
    assert report["labeled_suggestion_count"] == 0
    assert report["unlabeled_suggestion_count"] == 1
    assert report["outbound_action_count"] == 0


def test_catalog_quality_thresholds_hold_for_seeded_refresh():
    metrics = catalog_quality_metrics(
        [
            {"url": "https://jobs.example.com/1", "canonical_url": "https://jobs.example.com/1"},
            {"url": "https://jobs.example.com/1?ref=dup", "canonical_url": "https://jobs.example.com/1"},
            {
                "url": "https://jobs.example.com/2",
                "canonical_url": "https://jobs.example.com/2",
                "closed_at": "2026-05-11T00:00:00+00:00",
                "hidden": False,
            },
            {
                "url": "https://jobs.example.com/3",
                "canonical_url": "https://jobs.example.com/3",
                "closed_at": "2026-05-14T00:00:00+00:00",
                "hidden": False,
            },
        ],
        now=datetime(2026, 5, 14, 12, tzinfo=timezone.utc),
    )

    assert metrics["duplicate_rate"] == 0.25
    assert metrics["target_duplicate_rate_max"] == 0.02
    assert metrics["stale_closed_visible_count"] == 1
    assert metrics["closed_hidden_after_hours"] == 48


def test_evaluate_product_metrics_reports_catalog_duplicate_and_stale_violations():
    violations = evaluate_product_metrics(
        {
            "catalog": {
                "jobs_seen": 10,
                "target_jobs_seen_min": 1,
                "duplicate_rate": 0.25,
                "target_duplicate_rate_max": 0.02,
                "stale_closed_visible_count": 2,
            }
        }
    )

    assert len(violations) == 2
    assert any("duplicate rate" in violation.casefold() for violation in violations)
    assert any("stale closed job" in violation.casefold() for violation in violations)
