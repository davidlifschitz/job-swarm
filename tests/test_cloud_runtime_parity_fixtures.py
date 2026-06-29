from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from ml_job_swarm.cloud_runtime import compare_runtime_parity
from ml_job_swarm.filtering import apply_rules
from ml_job_swarm.source_policy import classify_source_url

FIXTURES = Path(__file__).parent / "fixtures" / "cloud_parity"
P0_THRESHOLD = 0.99


def test_cloud_runtime_parity_fixtures_meet_p0_threshold():
    baseline = _load_json("baseline_decisions.json")
    report = compare_runtime_parity(
        local=baseline["decisions"],
        cloud=_compute_cloud_decisions(),
        p0_threshold=P0_THRESHOLD,
    )

    assert report["meets_p0"], (
        f"cloud parity match_rate={report['match_rate']:.4f} "
        f"below P0 threshold {P0_THRESHOLD}; mismatches={report['mismatches']}"
    )
    assert report["match_rate"] >= baseline["p0_match_rate"]


def _compute_cloud_decisions() -> list[dict[str, object]]:
    decisions: list[dict[str, object]] = []

    source_cases = _load_json("source_policy_cases.json")
    for case in source_cases["cases"]:
        decisions.append(
            {
                "id": case["id"],
                "decision": classify_source_url(str(case["url"])).mode,
            }
        )

    fit_cases = _load_json("fit_bucket_cases.json")
    profile_fixture = json.loads((FIXTURES / str(fit_cases["profile_fixture"])).read_text())
    profile = profile_fixture["profile"]
    bucket_mapping = fit_cases["bucket_mapping"]
    target_profile = SimpleNamespace(
        role=profile["preferences"]["role"]["answer"],
        titles=tuple(profile["keywords"].get("desired_titles", [])),
        level=profile["preferences"]["level"]["answer"],
        locations=tuple(profile["keywords"].get("locations", [])),
        work_mode=profile["preferences"]["work_mode"]["answer"],
        company_stage=profile["preferences"]["company_stage"]["answer"],
        keywords=tuple(profile["keywords"].get("desired_titles", [])),
    )

    for job in profile_fixture["jobs"]:
        rules_result = apply_rules(
            SimpleNamespace(
                title=job["title"],
                location_text=job["location_text"],
                remote_mode=job["remote_mode"],
                seniority=job["seniority"],
                description_text=job["description_text"],
                requirements_text=job["requirements_text"],
            ),
            SimpleNamespace(
                name=job["company"]["name"],
                stage=job["company"].get("stage"),
                categories=(),
                tags=(),
            ),
            target_profile,
        )
        decisions.append(
            {
                "id": f"fit-bucket:{job['external_id']}",
                "decision": bucket_mapping[rules_result.outcome],
            }
        )

    return decisions


def _load_json(name: str) -> dict[str, object]:
    return json.loads((FIXTURES / name).read_text())
