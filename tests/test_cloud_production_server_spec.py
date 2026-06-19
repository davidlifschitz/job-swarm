from pathlib import Path
import re


SPEC_PATH = (
    Path(__file__).resolve().parents[1] / "docs" / "cloud-production-server-goals.md"
)


def _spec_text() -> str:
    assert SPEC_PATH.exists(), "cloud production server goals spec is missing"
    return SPEC_PATH.read_text(encoding="utf-8")


def test_cloud_production_server_spec_has_required_behavior_sections():
    text = _spec_text()

    required_sections = [
        "# Cloud Production Server Goals",
        "## Production Target",
        "## Quantitative Goals",
        "## Server Behavior Contract",
        "## TDD Acceptance Plan",
    ]

    for section in required_sections:
        assert section in text


def test_cloud_production_server_spec_is_quantitative_and_compliance_bounded():
    text = _spec_text().lower()

    required_terms = [
        "availability",
        "latency",
        "durability",
        "observability",
        "security",
        "cost",
        "runtime parity",
        "manual final submit",
        "0 automated final submissions",
        "source policy",
    ]

    for term in required_terms:
        assert term in text

    quantitative_markers = re.findall(
        r"(?:(?:p50|p95|p99|rpo|rto)\s*[<=>]+|[<=>]=?\s*)?"
        r"(?:\d+(?:\.\d+)?%|\d+(?:\.\d+)?\s*(?:ms|seconds|minutes|hours|days|gb|mb|cpu|jobs|sources|runs|usd)|\\$\\d+(?:\.\d+)?)",
        text,
    )

    assert len(quantitative_markers) >= 40
