from __future__ import annotations

import re
from collections import Counter
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
ENV_TEMPLATE = REPO_ROOT / ".env.hosted.example"
DEPLOY_DOC = REPO_ROOT / "docs" / "tier2-hosted-web.md"

ENV_KEY_LINE = re.compile(r"^(?:#\s*)?([A-Z][A-Z0-9_]*)=")
TABLE_ROW = re.compile(r"^\|\s*`?([^|`]+)`?\s*\|\s*([^|]+)\|")
SUPABASE_WILDCARD_VARS = frozenset(
    {"SUPABASE_URL", "SUPABASE_ANON_KEY", "SUPABASE_SERVICE_ROLE_KEY"}
)


def _section_between(text: str, start_heading: str, end_heading: str) -> str:
    start = text.index(start_heading)
    end = text.index(end_heading, start)
    return text[start:end]


def _required_vars_from_deploy_doc(doc_text: str) -> set[str]:
    """Extract required env var names from deploy/env tables in tier2-hosted-web.md."""
    required: set[str] = set()

    web_section = _section_between(doc_text, "### 2. Railway web", "### 3.")
    for line in web_section.splitlines():
        match = TABLE_ROW.match(line.strip())
        if not match:
            continue
        var_name = match.group(1).strip()
        required_col = match.group(2).strip()
        if var_name == "Variable" or var_name.startswith("-"):
            continue
        if required_col in {"Yes", "Phase A", "Phase B"}:
            required.add(var_name)

    worker_section = _section_between(doc_text, "### 4. Cloud worker", "### 5.")
    for line in worker_section.splitlines():
        match = TABLE_ROW.match(line.strip())
        if not match:
            continue
        var_name = match.group(1).strip()
        if var_name == "Variable" or var_name.startswith("-"):
            continue
        if var_name.endswith("*"):
            required.update(SUPABASE_WILDCARD_VARS)
        else:
            required.add(var_name)

    return required


def _env_template_keys(path: Path) -> tuple[list[str], set[str]]:
    """Return active assignment keys (ordered) and all keys (active or commented)."""
    active_keys: list[str] = []
    all_keys: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        match = ENV_KEY_LINE.match(stripped)
        if not match:
            continue
        key = match.group(1)
        all_keys.add(key)
        if not stripped.startswith("#"):
            active_keys.append(key)
    return active_keys, all_keys


def test_hosted_env_template_covers_documented_required_vars():
    assert ENV_TEMPLATE.is_file(), ".env.hosted.example is missing"
    assert DEPLOY_DOC.is_file(), "docs/tier2-hosted-web.md is missing"

    required = _required_vars_from_deploy_doc(DEPLOY_DOC.read_text(encoding="utf-8"))
    _, template_keys = _env_template_keys(ENV_TEMPLATE)

    missing = sorted(required - template_keys)
    assert not missing, (
        "documented required env vars missing from .env.hosted.example: "
        + ", ".join(missing)
    )


def test_hosted_env_template_has_no_duplicate_active_keys():
    assert ENV_TEMPLATE.is_file(), ".env.hosted.example is missing"

    active_keys, _ = _env_template_keys(ENV_TEMPLATE)
    duplicates = sorted(key for key, count in Counter(active_keys).items() if count > 1)

    assert duplicates == [], (
        "unexpected duplicate active keys in .env.hosted.example: "
        + ", ".join(duplicates)
    )
