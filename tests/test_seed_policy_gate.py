from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from ml_job_swarm.product_goals import (
    PRODUCT_SOURCE_STATUSES,
    audit_seed_sources,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
SEED_COMPANIES_PATH = REPO_ROOT / "data" / "seed_companies.json"
EXPECTED_SEED_SOURCE_COUNT = 82


def _load_seed_audit_records():
    seed_companies = json.loads(SEED_COMPANIES_PATH.read_text())
    return audit_seed_sources(seed_companies)


def test_seed_catalog_sources_have_explicit_policy_classification():
    records = _load_seed_audit_records()

    assert records
    assert all(record.status in PRODUCT_SOURCE_STATUSES for record in records)
    assert all(record.next_action for record in records)


def test_seed_catalog_all_sources_are_supported():
    records = _load_seed_audit_records()
    status_counts = Counter(record.status for record in records)

    assert len(records) == EXPECTED_SEED_SOURCE_COUNT, (
        f"expected {EXPECTED_SEED_SOURCE_COUNT} seed sources, "
        f"got {len(records)}; counts by status: {dict(status_counts)}"
    )
    assert status_counts == {"supported": EXPECTED_SEED_SOURCE_COUNT}, (
        f"seed catalog must be fully supported; counts by status: {dict(status_counts)}"
    )


def test_seed_catalog_has_no_blocked_or_needs_review_sources():
    records = _load_seed_audit_records()
    disallowed = [
        record
        for record in records
        if record.status in {"blocked", "needs_review"}
    ]

    assert disallowed == []
