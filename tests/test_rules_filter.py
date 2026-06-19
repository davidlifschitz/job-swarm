from ml_job_swarm.filtering import Company, Job, TargetProfile, apply_rules


def base_company() -> Company:
    return Company(name="Example AI", categories=("ai",), tags=("platform",), stage="growth")


def ml_profile(**overrides) -> TargetProfile:
    values = {
        "role": "Machine Learning Engineer",
        "titles": ("Machine Learning Engineer", "ML Engineer"),
        "level": "mid",
        "locations": ("New York",),
        "work_mode": "remote",
        "company_stage": "growth",
        "keywords": ("python", "pytorch", "llm"),
    }
    values.update(overrides)
    return TargetProfile(**values)


def test_role_match_passes():
    job = Job(
        title="Machine Learning Engineer",
        location_text="Remote - New York, NY",
        remote_mode="remote",
        seniority="mid",
        description_text="Build LLM products with Python and PyTorch.",
    )

    result = apply_rules(job, base_company(), ml_profile())

    assert result.outcome == "pass"
    assert result.score >= 80
    assert "role_match" in result.reasons


def test_adjacent_role_soft_passes():
    job = Job(
        title="AI Research Engineer",
        location_text="Remote - New York, NY",
        remote_mode="remote",
        seniority="mid",
        requirements_text="Python, PyTorch, and model evaluation experience.",
    )

    result = apply_rules(job, base_company(), ml_profile())

    assert result.outcome == "soft_pass"
    assert "adjacent_role" in result.reasons


def test_clear_unrelated_role_rejects():
    job = Job(
        title="Product Marketing Manager",
        location_text="Remote - New York, NY",
        remote_mode="remote",
        seniority="mid",
        description_text="Own launches, campaigns, and messaging.",
    )

    result = apply_rules(job, base_company(), ml_profile())

    assert result.outcome == "reject"
    assert "role_mismatch" in result.risks


def test_seniority_mismatch_soft_passes_for_llm_review_when_skills_match():
    job = Job(
        title="Senior Machine Learning Engineer",
        location_text="Remote - New York, NY",
        remote_mode="remote",
        seniority="senior",
        requirements_text="Python, PyTorch, LLM evaluation, and model serving.",
    )

    result = apply_rules(job, base_company(), ml_profile(level="mid"))

    assert result.outcome == "soft_pass"
    assert "seniority_mismatch" in result.risks
    assert "skills_match" in result.reasons


def test_explicit_location_mismatch_rejects():
    job = Job(
        title="Machine Learning Engineer",
        location_text="Berlin, Germany",
        remote_mode="onsite",
        seniority="mid",
        requirements_text="Python and PyTorch.",
    )

    result = apply_rules(job, base_company(), ml_profile(locations=("New York",)))

    assert result.outcome == "reject"
    assert "location_mismatch" in result.risks


def test_unknown_work_mode_soft_passes():
    job = Job(
        title="Machine Learning Engineer",
        location_text="New York, NY",
        remote_mode=None,
        seniority="mid",
        requirements_text="Python and PyTorch.",
    )

    result = apply_rules(job, base_company(), ml_profile(work_mode="remote"))

    assert result.outcome == "soft_pass"
    assert "unknown_work_mode" in result.risks


def test_normalized_remote_work_modes_match():
    job = Job(
        title="Machine Learning Engineer",
        location_text="Remote - New York, NY",
        remote_mode="remote-first",
        seniority="mid",
        requirements_text="Python and PyTorch.",
    )

    result = apply_rules(job, base_company(), ml_profile(work_mode="remote"))

    assert result.outcome == "pass"
    assert "work_mode_mismatch" not in result.risks


def test_normalized_onsite_work_modes_match():
    job = Job(
        title="Machine Learning Engineer",
        location_text="New York, NY",
        remote_mode="in-office",
        seniority="mid",
        requirements_text="Python and PyTorch.",
    )

    result = apply_rules(job, base_company(), ml_profile(work_mode="on-site"))

    assert result.outcome == "pass"
    assert "work_mode_mismatch" not in result.risks
