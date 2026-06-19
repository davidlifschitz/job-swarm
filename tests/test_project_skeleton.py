import importlib.metadata

import ml_job_swarm


def test_package_imports():
    assert ml_job_swarm.__all__ == ["__version__"]


def test_project_metadata_exists():
    assert importlib.metadata.metadata("ml-job-swarm")["Name"] == "ml-job-swarm"


def test_pdf_and_docx_parser_dependencies_are_packaged():
    requirements = importlib.metadata.requires("ml-job-swarm") or []

    assert any(requirement.lower().startswith("pymupdf") for requirement in requirements)
    assert any(
        requirement.lower().startswith("python-docx")
        for requirement in requirements
    )
