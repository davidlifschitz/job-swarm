import pytest

from ml_job_swarm.resume_storage import (
    SUPABASE_RESUME_URI_PREFIX,
    LocalResumeStorage,
    SupabaseResumeStorage,
    resume_storage_from_env,
)
from ml_job_swarm.resume_assets import (
    ResumeAssetStorageError,
    load_resume_asset_bytes,
    persist_resume_asset,
)


def test_resume_storage_from_env_defaults_to_local(tmp_path, monkeypatch):
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    monkeypatch.delenv("SUPABASE_SECRET_KEY", raising=False)
    backend = resume_storage_from_env(
        {"ML_JOB_SWARM_RESUME_ASSET_DIR": str(tmp_path)}
    )
    assert isinstance(backend, LocalResumeStorage)


def test_resume_storage_from_env_uses_supabase_when_configured(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-role-key")
    backend = resume_storage_from_env()
    assert isinstance(backend, SupabaseResumeStorage)


def test_supabase_persist_and_load_round_trip(monkeypatch):
    bucket = "resume-assets"
    store: dict[str, bytes] = {}

    class FakeResponse:
        def __init__(self, *, status_code: int, content: bytes = b"") -> None:
            self.status_code = status_code
            self.content = content

        def raise_for_status(self) -> None:
            if self.status_code >= 400:
                raise RuntimeError(f"http {self.status_code}")

    def fake_post(url: str, *, content: bytes, headers: dict[str, str], timeout: float):
        assert url.endswith("/storage/v1/object/resume-assets/user-a/abc123.pdf")
        assert headers["Authorization"] == "Bearer service-role-key"
        assert headers["x-upsert"] == "true"
        store["user-a/abc123.pdf"] = content
        return FakeResponse(status_code=200)

    def fake_get(url: str, *, headers: dict[str, str], timeout: float):
        assert url.endswith("/storage/v1/object/resume-assets/user-a/abc123.pdf")
        return FakeResponse(status_code=200, content=store["user-a/abc123.pdf"])

    monkeypatch.setattr("httpx.post", fake_post)
    monkeypatch.setattr("httpx.get", fake_get)

    backend = SupabaseResumeStorage(
        supabase_url="https://example.supabase.co",
        service_role_key="service-role-key",
        bucket=bucket,
    )
    uri = backend.persist(
        b"%PDF-1.4 resume",
        original_filename="resume.pdf",
        digest="abc123",
        user_id="user-a",
    )
    assert uri == f"{SUPABASE_RESUME_URI_PREFIX}user-a/abc123.pdf"
    assert backend.load_bytes(uri) == b"%PDF-1.4 resume"


def test_persist_resume_asset_uses_supabase_backend_when_configured(monkeypatch):
    calls: list[str] = []

    class FakeResponse:
        status_code = 200

        def raise_for_status(self) -> None:
            return None

    def fake_post(url: str, **kwargs):
        calls.append(url)
        return FakeResponse()

    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-role-key")
    monkeypatch.setattr("httpx.post", fake_post)

    uri = persist_resume_asset(
        b"%PDF-1.4 hosted",
        original_filename="resume.pdf",
        digest="hosted123",
        user_id="owner-1",
    )

    assert uri == f"{SUPABASE_RESUME_URI_PREFIX}owner-1/hosted123.pdf"
    assert calls


def test_load_resume_asset_bytes_rejects_unknown_uri_prefix(tmp_path):
    with pytest.raises(ResumeAssetStorageError, match="Unsupported"):
        load_resume_asset_bytes("s3://bucket/object", tmp_path)