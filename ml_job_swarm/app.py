from __future__ import annotations

import csv
import hashlib
import io
import json
import os
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated
from urllib.parse import urlencode

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader, select_autoescape
from pydantic import BaseModel, Field, ValidationError

from ml_job_swarm.adapters import public_ats_registry
from ml_job_swarm.api_v1 import create_api_v1_router
from ml_job_swarm.catalog import (
    infer_source_type,
    import_seed_companies,
    review_company_source,
    submit_company_source,
)
from ml_job_swarm.decisions import (
    clear_job_decision,
    record_job_decision,
    saved_job_export_rows,
)
from ml_job_swarm.auth_middleware import ACCESS_TOKEN_COOKIE, SupabaseAuthMiddleware
from ml_job_swarm.cloud_runtime import (
    ManualFinalSubmitBlocked,
    RunNotFound,
    build_runtime_readiness_report,
    cancel_run,
    create_manual_final_submit_instruction,
    create_run,
    evaluate_source_for_run,
    find_run_by_idempotency_key,
    get_run,
    get_run_for_user,
    list_run_events,
    list_runs,
    record_prepared_packet,
    record_run_heartbeat,
)
from ml_job_swarm.hosting import ensure_hosted_directories, hosted_paths_from_env, is_hosted_deployment
from ml_job_swarm.cloud_worker import run_cloud_workflow_once
from ml_job_swarm.filtering import (
    CompanyResult,
    JobFitResult,
    rules_preview_jobs,
    review_jobs_for_profile,
    review_jobs_for_profile_resilient,
    visible_company_results,
)
from ml_job_swarm.ingest import refresh_due_sources, refresh_source
from ml_job_swarm.linkedin_connections import (
    connections_for_company_id,
    connections_for_company_ids,
    grouped_connections_by_company,
    import_linkedin_connections,
    latest_import_summary,
    linkedin_connection_count,
    matched_catalog_companies,
    parse_linkedin_connections_csv,
)
from ml_job_swarm.llm import (
    LLMRequest,
    ResumeRewriteResponse,
    VisionFallbackResponse,
    record_llm_request,
    request_structured_response,
)
from ml_job_swarm.openrouter import configure_openrouter_clients_from_env
from ml_job_swarm.profile import (
    REQUIRED_PREFERENCE_IDS,
    ProfileAccessDenied,
    create_target_profile,
    current_profile_version,
    require_target_profile_access,
    update_preferences,
)
from ml_job_swarm.supabase_auth import supabase_config_from_env, validate_access_token
from ml_job_swarm.resume_assets import (
    ResumeAssetStorageError,
    default_resume_asset_dir,
    load_resume_asset_bytes,
    pdf_page_image_content_parts,
    persist_resume_asset,
)
from ml_job_swarm.resume_extract import (
    ResumeExtractionError,
    extract_text_from_bytes,
    parse_resume_text,
    record_parse_run,
)
from ml_job_swarm.source_policy import classify_source_url
from ml_job_swarm.store import connect, init_db


PACKAGE_ROOT = Path(__file__).parent
PROJECT_ROOT = PACKAGE_ROOT.parent
TEMPLATE_DIR = PACKAGE_ROOT / "web" / "templates"
STATIC_DIR = PACKAGE_ROOT / "web" / "static"
DEFAULT_SEED_COMPANIES_PATH = PROJECT_ROOT / "data" / "seed_companies.json"
SUPPORTED_RESUME_TYPES = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
}
_PREFERENCE_LABELS = {
    "role": "Role",
    "level": "Level",
    "location": "Location",
    "work_mode": "Work mode",
    "company_stage": "Company stage",
}
SENSITIVE_DETAIL_KEYS = {
    "authorization",
    "browser_profile",
    "cookie",
    "cookies",
    "private_prompt",
    "raw_prompt",
    "raw_resume_text",
    "resume_text",
    "secret",
    "token",
}
SENSITIVE_DETAIL_KEY_TERMS = (
    "auth",
    "browser_profile",
    "cookie",
    "key",
    "prompt",
    "resume",
    "secret",
    "session",
    "token",
)


class CloudRunCreateRequest(BaseModel):
    user_id: str | None = None
    requested_action: str
    input_manifest: dict[str, object] = Field(default_factory=dict)
    idempotency_key: str | None = None
    environment_class: str = "cloud"
    code_version: str = "unknown"
    container_image_digest: str = "unknown"
    dependency_lock_hash: str = "unknown"
    feature_flags: dict[str, object] = Field(default_factory=dict)


class CloudSourceEvaluationRequest(BaseModel):
    url: str


class CloudHeartbeatRequest(BaseModel):
    stage: str | None = None


class CloudCancelRequest(BaseModel):
    reason: str | None = None


class CloudPreparedPacketRequest(BaseModel):
    packet_manifest: dict[str, object]


class CloudFinalSubmitRequest(BaseModel):
    packet_id: str | None = None
    apply_url: str | None = None
    requested_by_automation: bool = False


class CloudContinueWorkflowRequest(BaseModel):
    user_id: str | None = None
    input_manifest: dict[str, object] = Field(default_factory=dict)
    idempotency_key: str | None = None
    environment_class: str = "cloud"
    code_version: str = "unknown"
    container_image_digest: str = "unknown"
    dependency_lock_hash: str = "unknown"
    feature_flags: dict[str, object] = Field(default_factory=dict)


def create_app(db_path: str | Path = ":memory:") -> FastAPI:
    app = FastAPI(title="ml-job-swarm")
    conn = connect(db_path, check_same_thread=False)
    init_db(conn)
    app.state.conn = conn
    app.state.db_path = str(db_path)
    app.state.adapter_registry = public_ats_registry()
    app.state.deployment_status = _deployment_status_from_env(os.environ)
    app.state.fit_gate_client = None
    app.state.resume_rewrite_client = None
    app.state.vision_fallback_provider = None
    app.state.resume_asset_dir = default_resume_asset_dir()
    configure_openrouter_clients_from_env(app)
    app.state.templates = Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=select_autoescape(["html", "xml"]),
    )

    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    app.state.supabase_auth_config = supabase_config_from_env()
    if app.state.supabase_auth_config is not None:
        app.add_middleware(SupabaseAuthMiddleware, config=app.state.supabase_auth_config)

    @app.get("/auth/login", response_class=HTMLResponse)
    def auth_login(request: Request, next: str = "/dashboard") -> HTMLResponse:
        if app.state.supabase_auth_config is None:
            return RedirectResponse("/dashboard", status_code=303)
        return _render(
            request,
            "login.html",
            supabase_url=app.state.supabase_auth_config.url,
            supabase_anon_key=app.state.supabase_auth_config.anon_key,
            next_path=next,
        )

    @app.post("/auth/callback")
    async def auth_callback(request: Request) -> JSONResponse:
        if app.state.supabase_auth_config is None:
            raise HTTPException(status_code=404, detail="auth not configured")
        payload = await request.json()
        token = str(payload.get("access_token") or "").strip()
        if not token:
            raise HTTPException(status_code=400, detail="access_token is required")
        try:
            validate_access_token(token, app.state.supabase_auth_config)
        except Exception as exc:
            raise HTTPException(status_code=401, detail="invalid access token") from exc
        response = JSONResponse({"ok": True})
        response.set_cookie(
            ACCESS_TOKEN_COOKIE,
            token,
            httponly=True,
            secure=is_hosted_deployment(),
            samesite="lax",
            max_age=60 * 60 * 24 * 7,
        )
        return response

    @app.get("/auth/logout")
    def auth_logout() -> RedirectResponse:
        response = RedirectResponse("/auth/login", status_code=303)
        response.delete_cookie(ACCESS_TOKEN_COOKIE)
        return response

    @app.get("/", include_in_schema=False)
    def root() -> RedirectResponse:
        return RedirectResponse("/onboarding", status_code=303)

    @app.get("/onboarding", response_class=HTMLResponse)
    def onboarding(
        request: Request,
        resume_asset_id: int | None = None,
        vision_fallback: str | None = None,
    ) -> HTMLResponse:
        return _render(
            request,
            "onboarding.html",
            resume_asset_id=resume_asset_id,
            vision_fallback_needed=vision_fallback == "needed",
            preference_ids=REQUIRED_PREFERENCE_IDS,
        )

    @app.post("/resume")
    async def upload_resume(
        resume: Annotated[UploadFile, File()],
    ) -> RedirectResponse:
        _require_supported_resume(resume)
        content = await resume.read()
        if not content:
            raise HTTPException(status_code=400, detail="Resume file is empty")

        digest = hashlib.sha256(content).hexdigest()
        storage_path = persist_resume_asset(
            content,
            original_filename=resume.filename or "resume",
            digest=digest,
            asset_dir=app.state.resume_asset_dir,
        )
        cursor = conn.execute(
            """
            INSERT OR IGNORE INTO resume_assets (
              original_filename,
              content_type,
              storage_path,
              sha256
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                resume.filename or "resume",
                resume.content_type or "",
                storage_path,
                digest,
            ),
        )
        conn.commit()
        if cursor.rowcount:
            resume_asset_id = int(cursor.lastrowid)
        else:
            row = conn.execute(
                "SELECT id FROM resume_assets WHERE sha256 = ?",
                (digest,),
            ).fetchone()
            resume_asset_id = int(row["id"])

        try:
            extracted_text = extract_text_from_bytes(content, resume.filename or "resume")
            parse_result = parse_resume_text(extracted_text)
            record_parse_run(
                conn,
                resume_asset_id=resume_asset_id,
                result=parse_result,
                consented_at=None,
            )
        except ResumeExtractionError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        redirect_url = f"/onboarding?resume_asset_id={resume_asset_id}"
        if parse_result.needs_vision_fallback:
            redirect_url += "&vision_fallback=needed"
        return RedirectResponse(redirect_url, status_code=303)

    @app.post("/resume/vision-fallback", response_class=HTMLResponse)
    async def consent_vision_fallback(
        request: Request,
        resume_asset_id: Annotated[int, Form()],
    ):
        pending_run = conn.execute(
            """
            SELECT id
            FROM resume_parse_runs
            WHERE resume_asset_id = ?
              AND status = 'needs_vision_fallback'
              AND vision_fallback_status = 'pending_consent'
            ORDER BY id DESC
            LIMIT 1
            """,
            (resume_asset_id,),
        ).fetchone()
        if pending_run is None:
            return HTMLResponse("No pending vision fallback", status_code=400)

        provider = request.app.state.vision_fallback_provider
        if provider is None:
            return HTMLResponse(
                "Vision fallback provider is not configured", status_code=503
            )

        asset = conn.execute(
            """
            SELECT original_filename, content_type, storage_path
            FROM resume_assets
            WHERE id = ?
            """,
            (resume_asset_id,),
        ).fetchone()
        if asset is None:
            return HTMLResponse("Resume asset not found", status_code=404)
        try:
            asset_content = load_resume_asset_bytes(
                asset["storage_path"],
                request.app.state.resume_asset_dir,
            )
            private_content_parts = pdf_page_image_content_parts(asset_content)
        except ResumeAssetStorageError as exc:
            return HTMLResponse(str(exc), status_code=502)

        consented_at = datetime.now(UTC)
        llm_request = LLMRequest(
            feature="resume_vision_fallback",
            schema_version=getattr(provider, "schema_version", "vision_fallback.v1"),
            model=getattr(provider, "model", "openrouter/vision"),
            input_reference=f"resume_asset:{resume_asset_id}",
            private_prompt=(
                "User consented to vision fallback for "
                f"resume_asset:{resume_asset_id} at {consented_at.isoformat()}. "
                "Extract resume text as strict JSON."
            ),
            private_content_parts=private_content_parts,
            provider=getattr(provider, "provider", "openrouter"),
        )
        try:
            response = request_structured_response(
                conn,
                provider,
                llm_request,
                VisionFallbackResponse,
            )
        except ValidationError:
            return HTMLResponse("Vision fallback response was invalid", status_code=502)

        conn.execute(
            """
            UPDATE resume_parse_runs
            SET vision_fallback_status = 'consented',
                vision_fallback_consented_at = ?
            WHERE id = ?
            """,
            (consented_at.isoformat(), pending_run["id"]),
        )
        conn.commit()

        parse_result = parse_resume_text(response.extracted_text)
        record_parse_run(
            conn,
            resume_asset_id=resume_asset_id,
            result=parse_result,
            consented_at=None,
        )
        return RedirectResponse(
            f"/onboarding?resume_asset_id={resume_asset_id}", status_code=303
        )

    @app.post("/resume/decline-vision-fallback", response_class=HTMLResponse)
    async def decline_vision_fallback(
        resume_asset_id: Annotated[int, Form()],
    ):
        pending_run = conn.execute(
            """
            SELECT id
            FROM resume_parse_runs
            WHERE resume_asset_id = ?
              AND status = 'needs_vision_fallback'
              AND vision_fallback_status = 'pending_consent'
            ORDER BY id DESC
            LIMIT 1
            """,
            (resume_asset_id,),
        ).fetchone()
        if pending_run is None:
            return HTMLResponse("No pending vision fallback", status_code=400)
        conn.execute(
            "UPDATE resume_parse_runs SET vision_fallback_status = 'declined' WHERE id = ?",
            (pending_run["id"],),
        )
        conn.commit()
        return RedirectResponse(
            f"/onboarding?resume_asset_id={resume_asset_id}", status_code=303
        )

    @app.post("/preferences", response_class=HTMLResponse)
    async def save_preferences(
        request: Request,
        resume_asset_id: Annotated[int | None, Form()] = None,
    ):
        form = await request.form()
        submitted = _submitted_preferences(form)
        missing = [pid for pid in REQUIRED_PREFERENCE_IDS if not submitted[pid]]
        if missing or resume_asset_id is None:
            errors = {
                pid: f"{_PREFERENCE_LABELS[pid]} is required."
                for pid in missing
            }
            form_error = (
                None
                if resume_asset_id is not None
                else "Upload a resume before saving preferences."
            )
            return _render(
                request,
                "onboarding.html",
                resume_asset_id=resume_asset_id,
                vision_fallback_needed=False,
                preference_ids=REQUIRED_PREFERENCE_IDS,
                errors=errors,
                form_error=form_error,
                submitted=submitted,
                status_code=400,
            )

        preferences = _preferences_payload(submitted)
        keywords = {
            "desired_titles": [str(form["role"])],
            "levels": [str(form["level"])],
            "locations": [str(form["location"])],
            "remote_modes": [str(form["work_mode"])],
            "company_stages": [str(form["company_stage"])],
        }
        target_profile_id = create_target_profile(
            conn,
            resume_asset_id=resume_asset_id,
            keywords=keywords,
            preferences=preferences,
            user_id=_authenticated_user_id(request),
        )
        return RedirectResponse(
            f"/dashboard?target_profile_id={target_profile_id}", status_code=303
        )

    @app.post("/preferences/{target_profile_id}", response_class=HTMLResponse)
    async def update_target_preferences(
        request: Request,
        target_profile_id: int,
    ):
        form = await request.form()
        submitted = _submitted_preferences(form)
        missing = [pid for pid in REQUIRED_PREFERENCE_IDS if not submitted[pid]]
        if missing:
            return HTMLResponse(
                "Missing required preference fields: " + ", ".join(missing),
                status_code=400,
            )
        preferences = _preferences_payload(submitted)
        _require_profile_access(request, target_profile_id)
        try:
            update_preferences(conn, target_profile_id, preferences)
        except ValueError as exc:
            return HTMLResponse(str(exc), status_code=400)
        return RedirectResponse(
            f"/dashboard?target_profile_id={target_profile_id}&preferences_status=updated",
            status_code=303,
        )

    @app.get("/connections", response_class=HTMLResponse)
    def connections_workspace(
        request: Request,
        search: str = "",
        import_status: str | None = None,
    ) -> HTMLResponse:
        user_id = _authenticated_user_id(request)
        return _render(
            request,
            "connections.html",
            connection_count=linkedin_connection_count(conn, user_id=user_id),
            latest_import=latest_import_summary(conn, user_id=user_id),
            grouped_companies=grouped_connections_by_company(
                conn, search=search, user_id=user_id
            ),
            matched_catalog=matched_catalog_companies(conn, user_id=user_id),
            search_query=search,
            import_status=import_status,
        )

    @app.post("/connections/import")
    async def import_connections_csv(
        request: Request,
        connections_file: Annotated[UploadFile, File()],
    ) -> RedirectResponse:
        content = await connections_file.read()
        if not content:
            return RedirectResponse(
                "/connections?import_status=empty",
                status_code=303,
            )
        try:
            parsed = parse_linkedin_connections_csv(content.decode("utf-8-sig"))
            result = import_linkedin_connections(
                conn,
                connections=parsed,
                filename=connections_file.filename or "Connections.csv",
                user_id=_authenticated_user_id(request),
            )
        except (UnicodeDecodeError, ValueError):
            return RedirectResponse(
                "/connections?import_status=invalid",
                status_code=303,
            )
        return RedirectResponse(
            (
                "/connections?import_status=success"
                f"&imported={result.imported}&updated={result.updated}"
            ),
            status_code=303,
        )

    @app.get("/dashboard", response_class=HTMLResponse)
    def dashboard(
        request: Request,
        target_profile_id: int | None = None,
        decision_filter: str = "all",
        connection_filter: str = "all",
    ) -> HTMLResponse:
        active_decision_filter = _dashboard_decision_filter(decision_filter)
        active_connection_filter = _dashboard_connection_filter(connection_filter)
        catalog_refreshed_at = _latest_succeeded_run_finished_at(conn)
        user_id = _authenticated_user_id(request)
        connection_count = linkedin_connection_count(conn, user_id=user_id)
        if target_profile_id is None:
            return _render(
                request,
                "dashboard.html",
                companies=[],
                connections_by_company_id={},
                profile_summary=None,
                resume_sections=[],
                resume_suggestions=[],
                decision_filter="all",
                connection_filter="all",
                connection_count=connection_count,
                onboarding_required=True,
                catalog_refreshed_at=catalog_refreshed_at,
                match_summary=None,
                fit_review_available=False,
                rules_preview_jobs=[],
                unreviewed_jobs=[],
            )
        _require_profile_access(request, target_profile_id)
        try:
            companies = visible_company_results(conn, target_profile_id)
            companies = _filter_companies_by_decision(
                companies, active_decision_filter
            )
            connections_by_company_id = connections_for_company_ids(
                conn,
                [company.company_id for company in companies],
                user_id=user_id,
            )
            companies = _filter_companies_by_connections(
                companies,
                connections_by_company_id,
                active_connection_filter,
            )
            companies = _sort_companies_by_connections(
                companies,
                connections_by_company_id,
            )
            profile_summary = _profile_summary(conn, target_profile_id)
            resume_sections = _resume_sections_for_profile(conn, target_profile_id)
            resume_suggestions = _resume_suggestions_for_profile(conn, target_profile_id)
            preview_jobs = rules_preview_jobs(conn, target_profile_id)
        except ValueError:
            return _render(
                request,
                "dashboard.html",
                companies=[],
                connections_by_company_id={},
                profile_summary=None,
                resume_sections=[],
                resume_suggestions=[],
                decision_filter="all",
                connection_filter="all",
                connection_count=connection_count,
                onboarding_required=True,
                catalog_refreshed_at=catalog_refreshed_at,
                match_summary=None,
                fit_review_available=False,
                rules_preview_jobs=[],
                unreviewed_jobs=[],
            )
        unreviewed_jobs = _unreviewed_job_rows(conn, target_profile_id)
        return _render(
            request,
            "dashboard.html",
            companies=companies,
            connections_by_company_id=connections_by_company_id,
            profile_summary=profile_summary,
            resume_sections=resume_sections,
            resume_suggestions=resume_suggestions,
            decision_filter=active_decision_filter,
            connection_filter=active_connection_filter,
            connection_count=connection_count,
            onboarding_required=False,
            catalog_refreshed_at=catalog_refreshed_at,
            match_summary=_match_summary_from_query(request.query_params),
            fit_review_available=app.state.fit_gate_client is not None,
            rules_preview_jobs=preview_jobs,
            unreviewed_jobs=unreviewed_jobs,
        )

    @app.get("/jobs/{job_id}", response_class=HTMLResponse)
    def job_detail(
        request: Request,
        job_id: int,
        target_profile_id: int | None = None,
    ) -> HTMLResponse:
        if target_profile_id is None:
            return HTMLResponse("target_profile_id is required", status_code=400)
        _require_profile_access(request, target_profile_id)
        try:
            detail = _job_detail(conn, job_id, target_profile_id)
        except ValueError as exc:
            return HTMLResponse(str(exc), status_code=400)
        if detail is None:
            return HTMLResponse("Job not found", status_code=404)
        return _render(
            request,
            "job_detail.html",
            job=detail,
            application_packet=_application_packet_for_job(
                conn,
                job_id=job_id,
                target_profile_id=target_profile_id,
            ),
            referral_contacts=_referral_contacts_for_job(conn, job_id=job_id),
            linkedin_connections=_linkedin_connections_for_job(
                conn,
                job_id=job_id,
                user_id=_authenticated_user_id(request),
            ),
            target_profile_id=target_profile_id,
        )

    @app.post("/jobs/{job_id}/referral-contacts")
    def add_referral_contact(
        request: Request,
        job_id: int,
        target_profile_id: Annotated[int | None, Form()] = None,
        name: Annotated[str | None, Form()] = None,
        email: Annotated[str | None, Form()] = None,
        title: Annotated[str | None, Form()] = None,
        relationship: Annotated[str | None, Form()] = None,
        notes: Annotated[str | None, Form()] = None,
    ):
        if target_profile_id is None:
            return HTMLResponse("target_profile_id is required", status_code=400)
        _require_profile_access(request, target_profile_id)
        if not name or not name.strip():
            return HTMLResponse("name is required", status_code=400)
        company_id = _company_id_for_job(conn, job_id)
        if company_id is None:
            return HTMLResponse("Job not found", status_code=404)
        _add_referral_contact(
            conn,
            company_id=company_id,
            name=name.strip(),
            email=(email or "").strip(),
            title=(title or "").strip(),
            relationship=(relationship or "").strip(),
            notes=(notes or "").strip(),
        )
        return RedirectResponse(
            f"/jobs/{job_id}?target_profile_id={target_profile_id}",
            status_code=303,
        )

    @app.post("/jobs/{job_id}/application-packet")
    def prepare_application_packet(
        request: Request,
        job_id: int,
        target_profile_id: Annotated[int | None, Form()] = None,
    ):
        if target_profile_id is None:
            return HTMLResponse("target_profile_id is required", status_code=400)
        _require_profile_access(request, target_profile_id)
        try:
            packet_id = _prepare_application_packet(
                conn,
                job_id=job_id,
                target_profile_id=target_profile_id,
            )
        except ValueError as exc:
            return HTMLResponse(str(exc), status_code=404)
        return RedirectResponse(
            f"/jobs/{job_id}?target_profile_id={target_profile_id}",
            status_code=303,
        )

    @app.post("/application-packets/{packet_id}/status")
    def update_application_packet_status(
        request: Request,
        packet_id: int,
        target_profile_id: Annotated[int | None, Form()] = None,
        status: Annotated[str | None, Form()] = None,
    ):
        if target_profile_id is None:
            return HTMLResponse("target_profile_id is required", status_code=400)
        _require_profile_access(request, target_profile_id)
        if status not in {"prepared", "submitted"}:
            return HTMLResponse("status must be prepared or submitted", status_code=400)
        row = conn.execute(
            """
            SELECT job_id
            FROM application_packets
            WHERE id = ?
              AND target_profile_id = ?
            """,
            (packet_id, target_profile_id),
        ).fetchone()
        if row is None:
            return HTMLResponse("Application packet not found", status_code=404)
        conn.execute(
            """
            UPDATE application_packets
            SET status = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (status, packet_id),
        )
        conn.commit()
        return RedirectResponse(
            f"/jobs/{row['job_id']}?target_profile_id={target_profile_id}",
            status_code=303,
        )

    @app.post("/jobs/{job_id}/decision")
    def set_job_decision(
        request: Request,
        job_id: int,
        target_profile_id: Annotated[int | None, Form()] = None,
        decision: Annotated[str | None, Form()] = None,
        notes: Annotated[str | None, Form()] = None,
        return_to: Annotated[str | None, Form()] = None,
    ):
        if target_profile_id is None:
            return HTMLResponse("target_profile_id is required", status_code=400)
        _require_profile_access(request, target_profile_id)
        if decision is None:
            return HTMLResponse("decision is required", status_code=400)
        try:
            if decision == "clear":
                clear_job_decision(
                    conn,
                    job_id=job_id,
                    target_profile_id=target_profile_id,
                )
            else:
                record_job_decision(
                    conn,
                    job_id=job_id,
                    target_profile_id=target_profile_id,
                    decision=decision,
                    notes=notes or "",
                )
        except ValueError as exc:
            return HTMLResponse(str(exc), status_code=400)
        fallback = f"/dashboard?target_profile_id={target_profile_id}"
        landing = _safe_return_path(return_to, fallback)
        status_value = "cleared" if decision == "clear" else decision
        landing = _append_query_param(landing, "decision_status", status_value)
        return RedirectResponse(landing, status_code=303)

    @app.post("/dashboard/review-jobs", response_class=HTMLResponse)
    def review_dashboard_jobs(
        request: Request,
        target_profile_id: Annotated[int | None, Form()] = None,
        llm_consent: Annotated[str | None, Form()] = None,
    ) -> HTMLResponse:
        if target_profile_id is None:
            return HTMLResponse("target_profile_id is required", status_code=400)
        _require_profile_access(request, target_profile_id)
        if llm_consent != "on":
            return HTMLResponse("LLM consent is required", status_code=400)
        fit_gate_client = app.state.fit_gate_client
        if fit_gate_client is None:
            return HTMLResponse("Fit review client unavailable", status_code=503)
        try:
            review_jobs_for_profile(conn, target_profile_id, fit_gate_client)
        except ValueError as exc:
            return HTMLResponse(str(exc), status_code=400)
        except Exception:
            return HTMLResponse(
                "Fit review failed. Check the configured LLM provider and retry.",
                status_code=502,
            )
        return RedirectResponse(
            f"/dashboard?target_profile_id={target_profile_id}", status_code=303
        )

    @app.post("/dashboard/refresh-sources", response_class=HTMLResponse)
    def refresh_dashboard_sources(
        request: Request,
        target_profile_id: Annotated[int | None, Form()] = None,
    ) -> HTMLResponse:
        if target_profile_id is None:
            return HTMLResponse("target_profile_id is required", status_code=400)
        _require_profile_access(request, target_profile_id)
        try:
            _profile_summary(conn, target_profile_id)
        except ValueError as exc:
            return HTMLResponse(str(exc), status_code=400)

        source_types = app.state.adapter_registry.source_types()
        skipped = _reviewed_source_count(conn) - _reviewed_source_count(
            conn,
            source_types,
        )
        summary = refresh_due_sources(
            conn,
            app.state.adapter_registry,
            source_types=source_types,
        )

        landing = f"/dashboard?target_profile_id={target_profile_id}"
        for key, value in {
            "refresh_status": "failed" if summary.failures else "completed",
            "sources_attempted": summary.sources_attempted,
            "sources_succeeded": summary.sources_succeeded,
            "sources_refreshed": summary.sources_refreshed,
            "sources_skipped": skipped,
            "jobs_seen": summary.jobs_seen,
            "jobs_closed": summary.jobs_closed,
            "suspicious_empty": summary.suspicious_empty,
            "reviews_created": 0,
            "review_failures": 0,
            "failures": summary.failures,
            "blocked": summary.blocked,
        }.items():
            landing = _append_query_param(landing, key, str(value))
        return RedirectResponse(landing, status_code=303)

    @app.post("/dashboard/find-matches", response_class=HTMLResponse)
    def find_dashboard_matches(
        request: Request,
        target_profile_id: Annotated[int | None, Form()] = None,
        llm_consent: Annotated[str | None, Form()] = None,
    ) -> HTMLResponse:
        if target_profile_id is None:
            return HTMLResponse("target_profile_id is required", status_code=400)
        _require_profile_access(request, target_profile_id)
        if llm_consent != "on":
            return HTMLResponse("LLM consent is required", status_code=400)
        fit_gate_client = app.state.fit_gate_client
        if fit_gate_client is None:
            return HTMLResponse("Fit review client unavailable", status_code=503)

        source_types = app.state.adapter_registry.source_types()
        skipped = _reviewed_source_count(conn) - _reviewed_source_count(
            conn,
            source_types,
        )
        summary = refresh_due_sources(
            conn,
            app.state.adapter_registry,
            source_types=source_types,
        )
        try:
            review_summary = review_jobs_for_profile_resilient(
                conn,
                target_profile_id,
                fit_gate_client,
            )
        except ValueError as exc:
            return HTMLResponse(str(exc), status_code=400)
        except Exception:
            return HTMLResponse(
                "Fit review failed. Check the configured LLM provider and retry.",
                status_code=502,
            )

        landing = f"/dashboard?target_profile_id={target_profile_id}"
        for key, value in {
            "match_status": (
                "failed" if summary.failures or review_summary.failures else "completed"
            ),
            "sources_attempted": summary.sources_attempted,
            "sources_succeeded": summary.sources_succeeded,
            "sources_refreshed": summary.sources_refreshed,
            "sources_skipped": skipped,
            "jobs_seen": summary.jobs_seen,
            "jobs_closed": summary.jobs_closed,
            "suspicious_empty": summary.suspicious_empty,
            "reviews_created": len(review_summary.review_ids),
            "review_failures": review_summary.failures,
            "failures": summary.failures,
            "blocked": summary.blocked,
        }.items():
            landing = _append_query_param(landing, key, str(value))
        return RedirectResponse(landing, status_code=303)

    @app.get("/dashboard/saved.csv")
    def export_saved_jobs(
        request: Request,
        target_profile_id: int | None = None,
        q: str = "",
        sort: str = "recent",
    ) -> Response:
        if target_profile_id is None:
            return HTMLResponse("target_profile_id is required", status_code=400)
        _require_profile_access(request, target_profile_id)
        try:
            rows = saved_job_export_rows(conn, target_profile_id)
        except ValueError as exc:
            return HTMLResponse(str(exc), status_code=400)
        sort_key = sort if sort in {"recent", "score", "company", "title"} else "recent"
        rows = _sort_saved_jobs(_filter_saved_jobs(rows, q.strip()), sort_key)

        output = io.StringIO()
        writer = csv.DictWriter(
            output,
            fieldnames=[
                "company",
                "title",
                "fit_score",
                "label",
                "recommendation",
                "packet_status",
                "manual_submit_url",
                "apply_url",
                "source_url",
                "decision",
                "notes",
                "decided_at",
            ],
            extrasaction="ignore",
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(_csv_safe_row(row))
        return Response(output.getvalue(), media_type="text/csv")

    @app.get("/dashboard/saved", response_class=HTMLResponse)
    def saved_jobs(
        request: Request,
        target_profile_id: int | None = None,
        q: str = "",
        sort: str = "recent",
    ) -> HTMLResponse:
        if target_profile_id is None:
            return HTMLResponse("target_profile_id is required", status_code=400)
        _require_profile_access(request, target_profile_id)
        try:
            rows = saved_job_export_rows(conn, target_profile_id)
        except ValueError as exc:
            return HTMLResponse(str(exc), status_code=400)
        sort_key = sort if sort in {"recent", "score", "company", "title"} else "recent"
        query = q.strip()
        filtered_rows = _sort_saved_jobs(_filter_saved_jobs(rows, query), sort_key)
        contacts_by_job_id = _referral_contacts_by_job_id(
            conn,
            [int(row["job_id"]) for row in filtered_rows],
        )
        for row in filtered_rows:
            row["referral_contacts"] = contacts_by_job_id.get(int(row["job_id"]), [])
        return _render(
            request,
            "saved_jobs.html",
            saved_jobs=filtered_rows,
            has_saved_jobs=bool(rows),
            has_filters=bool(query) or sort_key != "recent",
            query=query,
            sort=sort_key,
            target_profile_id=target_profile_id,
        )

    @app.get("/sources/new", response_class=HTMLResponse)
    def new_source(
        request: Request,
        company_name: str = "",
        source_url: str = "",
    ) -> HTMLResponse:
        company_name = company_name.strip()
        source_url = source_url.strip()
        return _render(
            request,
            "source_new.html",
            company_name=company_name,
            source_url=source_url,
            preflight=_source_intake_preview(
                company_name,
                source_url,
                app.state.adapter_registry.source_types(),
            ),
        )

    @app.post("/sources/new")
    def submit_new_source(
        company_name: Annotated[str | None, Form()] = None,
        source_url: Annotated[str | None, Form()] = None,
    ):
        if not (company_name or "").strip() or not (source_url or "").strip():
            return HTMLResponse(
                "company_name and source_url are required",
                status_code=400,
            )
        submit_company_source(conn, company_name.strip(), source_url.strip())
        return RedirectResponse("/admin/sources", status_code=303)

    @app.post("/resume/rewrite", response_class=HTMLResponse)
    async def rewrite_resume_section(
        section_id: Annotated[int | None, Form()] = None,
        target_profile_id: Annotated[int | None, Form()] = None,
        job_id: Annotated[int | None, Form()] = None,
        llm_consent: Annotated[str | None, Form()] = None,
    ) -> HTMLResponse:
        if section_id is None:
            return HTMLResponse("section_id is required", status_code=400)
        if llm_consent != "on":
            return HTMLResponse("LLM consent is required", status_code=400)

        rewrite_client = app.state.resume_rewrite_client
        if rewrite_client is None:
            return HTMLResponse("Resume rewrite client unavailable", status_code=503)

        section = _resume_section(conn, section_id)
        if section is None:
            return HTMLResponse("Resume section not found", status_code=404)

        payload = {
            "section_id": section_id,
            "target_profile_id": target_profile_id,
            "job_id": job_id,
            "heading": section["heading"],
            "section_type": section["section_type"],
            "text": section["text"],
        }
        llm_request = LLMRequest(
            feature="resume_rewrite",
            schema_version=getattr(
                rewrite_client, "schema_version", "resume_rewrite.v1"
            ),
            model=getattr(rewrite_client, "model", "unknown"),
            provider=getattr(rewrite_client, "provider", "openrouter"),
            input_reference=(
                f"resume_asset:{section['resume_asset_id']}|section:{section_id}"
            ),
            private_prompt=str(section["text"]),
        )
        raw_response = {}
        try:
            raw_response = rewrite_client.rewrite_section(payload)
            response = ResumeRewriteResponse.model_validate(raw_response)
        except Exception as exc:
            record_llm_request(
                conn,
                llm_request,
                status="failed",
                response_payload=raw_response if isinstance(raw_response, dict) else {},
                error="response validation failed"
                if isinstance(exc, ValidationError)
                else str(exc),
            )
            return HTMLResponse("Resume rewrite failed", status_code=502)

        llm_request_id = record_llm_request(
            conn,
            llm_request,
            status="succeeded",
            response_payload=response.model_dump(),
        )
        cursor = conn.execute(
            """
            INSERT INTO resume_rewrite_suggestions (
              resume_asset_id,
              job_id,
              target_profile_id,
              section_id,
              llm_request_id,
              suggestion_text,
              status
            )
            VALUES (?, ?, ?, ?, ?, ?, 'draft')
            """,
            (
                section["resume_asset_id"],
                job_id,
                target_profile_id,
                section_id,
                llm_request_id,
                response.replacement_text,
            ),
        )
        conn.commit()
        if target_profile_id is not None:
            return RedirectResponse(
                f"/dashboard?target_profile_id={target_profile_id}",
                status_code=303,
            )
        return HTMLResponse(
            f"Resume rewrite suggestion created: {int(cursor.lastrowid)}"
        )

    @app.post("/resume/suggestions/{suggestion_id}/accept", response_class=HTMLResponse)
    def accept_resume_suggestion(
        suggestion_id: int,
        target_profile_id: Annotated[int | None, Form()] = None,
    ):
        updated = _update_resume_suggestion_status(
            conn, suggestion_id, "accepted", target_profile_id
        )
        if not updated:
            return HTMLResponse("Suggestion not found", status_code=404)
        if target_profile_id is not None:
            return RedirectResponse(
                f"/dashboard?target_profile_id={target_profile_id}",
                status_code=303,
            )
        return HTMLResponse("Suggestion accepted")

    @app.post("/resume/suggestions/{suggestion_id}/reject", response_class=HTMLResponse)
    def reject_resume_suggestion(
        suggestion_id: int,
        target_profile_id: Annotated[int | None, Form()] = None,
    ):
        updated = _update_resume_suggestion_status(
            conn, suggestion_id, "rejected", target_profile_id
        )
        if not updated:
            return HTMLResponse("Suggestion not found", status_code=404)
        if target_profile_id is not None:
            return RedirectResponse(
                f"/dashboard?target_profile_id={target_profile_id}",
                status_code=303,
            )
        return HTMLResponse("Suggestion rejected")

    @app.get("/admin/sources", response_class=HTMLResponse)
    def admin_sources(request: Request) -> HTMLResponse:
        source_rows = _source_health_rows(
            conn,
            app.state.adapter_registry.source_types(),
        )
        return _render(
            request,
            "admin_sources.html",
            source_reviews=_source_review_rows(
                conn,
                app.state.adapter_registry.source_types(),
            ),
            sources=source_rows,
            source_support_summary=_source_support_summary(source_rows),
        )

    @app.post("/admin/source-review/{queue_id}/approve")
    def approve_source_review(queue_id: int):
        try:
            review_company_source(conn, queue_id, "approve")
        except ValueError as exc:
            return HTMLResponse(str(exc), status_code=400)
        return RedirectResponse("/admin/sources", status_code=303)

    @app.post("/admin/source-review/{queue_id}/approve-refresh")
    def approve_source_review_and_refresh(queue_id: int):
        try:
            result = review_company_source(conn, queue_id, "approve")
        except ValueError as exc:
            return HTMLResponse(str(exc), status_code=400)

        source_id = result.get("job_source_id")
        if source_id is None:
            return RedirectResponse("/admin/sources", status_code=303)

        source = conn.execute(
            "SELECT source_type FROM job_sources WHERE id = ?",
            (source_id,),
        ).fetchone()
        source_types = app.state.adapter_registry.source_types()
        if source is None or source["source_type"] not in source_types:
            return _admin_runs_summary_redirect(
                refresh_status="completed",
                sources_seen=0,
                sources_attempted=0,
                sources_succeeded=0,
                sources_refreshed=0,
                sources_skipped=1,
                jobs_seen=0,
                jobs_closed=0,
                suspicious_empty=0,
                failures=0,
                blocked=0,
            )

        refresh_result = refresh_source(
            conn,
            int(source_id),
            app.state.adapter_registry.adapter_for(source["source_type"]),
        )
        return _admin_runs_summary_redirect(
            refresh_status=(
                "failed" if refresh_result.status == "failed" else "completed"
            ),
            sources_seen=1,
            sources_attempted=1,
            sources_succeeded=int(refresh_result.status == "succeeded"),
            sources_refreshed=int(refresh_result.status == "succeeded"),
            sources_skipped=0,
            jobs_seen=refresh_result.jobs_seen,
            jobs_closed=refresh_result.jobs_closed,
            suspicious_empty=int(refresh_result.status == "suspicious_empty"),
            failures=int(refresh_result.status == "failed"),
            blocked=int(refresh_result.status == "blocked"),
        )

    @app.post("/admin/source-review/{queue_id}/reject")
    def reject_source_review(queue_id: int):
        try:
            review_company_source(conn, queue_id, "reject")
        except ValueError as exc:
            return HTMLResponse(str(exc), status_code=400)
        return RedirectResponse("/admin/sources", status_code=303)

    @app.post("/admin/sources/refresh")
    def refresh_admin_sources():
        source_types = app.state.adapter_registry.source_types()
        skipped = _reviewed_source_count(conn) - _reviewed_source_count(
            conn,
            source_types,
        )
        summary = refresh_due_sources(
            conn,
            app.state.adapter_registry,
            source_types=source_types,
        )
        return _admin_runs_summary_redirect(
            refresh_status="failed" if summary.failures else "completed",
            sources_seen=summary.sources_seen,
            sources_attempted=summary.sources_attempted,
            sources_succeeded=summary.sources_succeeded,
            sources_refreshed=summary.sources_refreshed,
            sources_skipped=skipped,
            jobs_seen=summary.jobs_seen,
            jobs_closed=summary.jobs_closed,
            suspicious_empty=summary.suspicious_empty,
            failures=summary.failures,
            blocked=summary.blocked,
        )

    @app.post("/admin/sources/{source_id}/refresh")
    def refresh_admin_source(source_id: int):
        source = conn.execute(
            """
            SELECT source_type, disabled_at
            FROM job_sources
            WHERE id = ?
            """,
            (source_id,),
        ).fetchone()
        if source is None:
            return HTMLResponse("Source not found", status_code=404)
        if source["disabled_at"] is not None:
            return HTMLResponse("Source disabled", status_code=400)

        source_types = app.state.adapter_registry.source_types()
        if source["source_type"] not in source_types:
            return _admin_runs_summary_redirect(
                refresh_status="completed",
                sources_seen=0,
                sources_attempted=0,
                sources_succeeded=0,
                sources_refreshed=0,
                sources_skipped=1,
                jobs_seen=0,
                jobs_closed=0,
                suspicious_empty=0,
                failures=0,
                blocked=0,
            )

        refresh_result = refresh_source(
            conn,
            source_id,
            app.state.adapter_registry.adapter_for(source["source_type"]),
        )
        return _admin_runs_summary_redirect(
            refresh_status=(
                "failed" if refresh_result.status == "failed" else "completed"
            ),
            sources_seen=1,
            sources_attempted=1,
            sources_succeeded=int(refresh_result.status == "succeeded"),
            sources_refreshed=int(refresh_result.status == "succeeded"),
            sources_skipped=0,
            jobs_seen=refresh_result.jobs_seen,
            jobs_closed=refresh_result.jobs_closed,
            suspicious_empty=int(refresh_result.status == "suspicious_empty"),
            failures=int(refresh_result.status == "failed"),
            blocked=int(refresh_result.status == "blocked"),
        )

    @app.get("/admin/audit", response_class=HTMLResponse)
    def admin_audit(request: Request) -> HTMLResponse:
        return _render(
            request,
            "admin_audit.html",
            audit_events=_admin_audit_rows(conn),
        )

    @app.get("/admin/runs", response_class=HTMLResponse)
    def admin_runs(request: Request) -> HTMLResponse:
        return _render(
            request,
            "admin_runs.html",
            runs=_ingestion_run_rows(conn),
        )

    @app.get("/admin/runs/{run_id}", response_class=HTMLResponse)
    def admin_run_detail(request: Request, run_id: int) -> HTMLResponse:
        run = _ingestion_run_detail(conn, run_id)
        if run is None:
            return HTMLResponse("Run not found", status_code=404)
        return _render(
            request,
            "admin_run_detail.html",
            run=run,
            friction_events=_run_friction_rows(conn, run_id),
            snapshots=_run_snapshot_rows(conn, run_id),
        )

    @app.post("/admin/sources/{source_id}/disable")
    def disable_source(source_id: int):
        before = conn.execute(
            "SELECT disabled_at FROM job_sources WHERE id = ?",
            (source_id,),
        ).fetchone()
        if before is None:
            return HTMLResponse("Source not found", status_code=404)

        conn.execute(
            "UPDATE job_sources SET disabled_at = CURRENT_TIMESTAMP WHERE id = ?",
            (source_id,),
        )
        after = conn.execute(
            "SELECT disabled_at FROM job_sources WHERE id = ?",
            (source_id,),
        ).fetchone()
        conn.execute(
            """
            INSERT INTO admin_audit_events (
              action,
              target_type,
              target_id,
              before_json,
              after_json
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                "disable",
                "job_source",
                str(source_id),
                json.dumps({"disabled_at": before["disabled_at"]}, sort_keys=True),
                json.dumps({"disabled_at": after["disabled_at"]}, sort_keys=True),
            ),
        )
        conn.commit()
        return RedirectResponse("/admin/sources", status_code=303)

    @app.post("/admin/sources/{source_id}/enable")
    def enable_source(source_id: int):
        before = conn.execute(
            "SELECT disabled_at FROM job_sources WHERE id = ?",
            (source_id,),
        ).fetchone()
        if before is None:
            return HTMLResponse("Source not found", status_code=404)

        conn.execute(
            "UPDATE job_sources SET disabled_at = NULL WHERE id = ?",
            (source_id,),
        )
        after = conn.execute(
            "SELECT disabled_at FROM job_sources WHERE id = ?",
            (source_id,),
        ).fetchone()
        conn.execute(
            """
            INSERT INTO admin_audit_events (
              action,
              target_type,
              target_id,
              before_json,
              after_json
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                "enable",
                "job_source",
                str(source_id),
                json.dumps({"disabled_at": before["disabled_at"]}, sort_keys=True),
                json.dumps({"disabled_at": after["disabled_at"]}, sort_keys=True),
            ),
        )
        conn.commit()
        return RedirectResponse("/admin/sources", status_code=303)

    @app.get("/admin/sources/friction", response_class=HTMLResponse)
    def source_friction(request: Request) -> HTMLResponse:
        return _render(
            request,
            "source_friction.html",
            friction_events=_friction_export_rows(conn),
        )

    @app.post("/admin/sources/friction/{event_id}/review")
    def review_source_friction(
        event_id: int,
        review_status: Annotated[str | None, Form()] = None,
        review_note: Annotated[str | None, Form()] = None,
    ):
        if review_status not in {"reviewed", "resolved"}:
            return HTMLResponse("Invalid review status", status_code=400)
        before = conn.execute(
            """
            SELECT review_status, review_note
            FROM source_friction_events
            WHERE id = ?
            """,
            (event_id,),
        ).fetchone()
        if before is None:
            return HTMLResponse("Friction event not found", status_code=404)

        sanitized_note = _sanitize_review_note(review_note)
        conn.execute(
            """
            UPDATE source_friction_events
            SET
              review_status = ?,
              reviewed_at = CURRENT_TIMESTAMP,
              reviewed_by = ?,
              review_note = ?
            WHERE id = ?
            """,
            (review_status, "local-admin", sanitized_note, event_id),
        )
        conn.execute(
            """
            INSERT INTO admin_audit_events (
              action,
              target_type,
              target_id,
              before_json,
              after_json
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                "review_friction",
                "source_friction_event",
                str(event_id),
                json.dumps(
                    {
                        "review_note": before["review_note"],
                        "review_status": before["review_status"],
                    },
                    sort_keys=True,
                ),
                json.dumps(
                    {
                        "review_note": sanitized_note,
                        "review_status": review_status,
                    },
                    sort_keys=True,
                ),
            ),
        )
        conn.commit()
        return RedirectResponse("/admin/sources/friction", status_code=303)

    @app.get("/admin/sources/friction.csv")
    def export_friction_csv() -> Response:
        output = io.StringIO()
        writer = csv.DictWriter(
            output,
            fieldnames=[
                "company",
                "source_url",
                "event_type",
                "status_code",
                "details_json",
                "review_status",
                "reviewed_at",
                "reviewed_by",
                "review_note",
                "created_at",
            ],
            extrasaction="ignore",
        )
        writer.writeheader()
        for row in _friction_export_rows(conn):
            writer.writerow(_csv_safe_row(row))
        return Response(output.getvalue(), media_type="text/csv")

    @app.get("/healthz")
    def healthz():
        report = build_runtime_readiness_report(conn)
        return {
            "status": report["status"],
            "service": report["service"],
            "database": report["database"],
            "slo_targets": report["slo_targets"],
        }

    @app.get("/api/cloud/readiness")
    def cloud_readiness():
        return build_runtime_readiness_report(conn)

    @app.get("/api/cloud/runs")
    def list_cloud_runs(http_request: Request):
        user_id = _authenticated_user_id(http_request)
        return {
            "runs": [
                {**run, "events": list_run_events(conn, str(run["id"]))}
                for run in list_runs(conn, user_id=user_id)
            ]
        }

    @app.post("/api/cloud/worker/run-next")
    def run_next_cloud_workflow():
        return run_cloud_workflow_once(
            conn,
            adapter_registry=app.state.adapter_registry,
            fit_gate_client=app.state.fit_gate_client,
        )

    @app.post("/api/cloud/workflows/continue")
    def continue_cloud_workflow(
        body: CloudContinueWorkflowRequest, http_request: Request
    ):
        user_id = _resolve_cloud_user_id(http_request, body.user_id)
        existing = find_run_by_idempotency_key(conn, user_id, body.idempotency_key)
        if existing is None:
            run = create_run(
                conn,
                user_id=user_id,
                requested_action="continue_local_workflow",
                input_manifest=body.input_manifest,
                idempotency_key=body.idempotency_key,
                environment_class=body.environment_class,
                code_version=body.code_version,
                container_image_digest=body.container_image_digest,
                dependency_lock_hash=body.dependency_lock_hash,
                feature_flags=body.feature_flags,
            )
            run_id = str(run["id"])
        else:
            run_id = str(existing["id"])
        return run_cloud_workflow_once(
            conn,
            adapter_registry=app.state.adapter_registry,
            fit_gate_client=app.state.fit_gate_client,
            run_id=run_id,
        )

    @app.post("/api/cloud/runs")
    def create_cloud_run(body: CloudRunCreateRequest, http_request: Request):
        user_id = _resolve_cloud_user_id(http_request, body.user_id)
        existing = find_run_by_idempotency_key(conn, user_id, body.idempotency_key)
        if existing is not None:
            return existing
        run = create_run(
            conn,
            user_id=user_id,
            requested_action=body.requested_action,
            input_manifest=body.input_manifest,
            idempotency_key=body.idempotency_key,
            environment_class=body.environment_class,
            code_version=body.code_version,
            container_image_digest=body.container_image_digest,
            dependency_lock_hash=body.dependency_lock_hash,
            feature_flags=body.feature_flags,
        )
        return JSONResponse(status_code=201, content=run)

    @app.get("/api/cloud/runs/{run_id}")
    def get_cloud_run(run_id: str, http_request: Request):
        try:
            run = _get_cloud_run(conn, run_id, http_request)
        except RunNotFound as exc:
            raise HTTPException(status_code=404, detail="cloud run not found") from exc
        return {**run, "events": list_run_events(conn, run_id)}

    @app.post("/api/cloud/runs/{run_id}/heartbeat")
    def heartbeat_cloud_run(
        run_id: str, body: CloudHeartbeatRequest, http_request: Request
    ):
        try:
            _get_cloud_run(conn, run_id, http_request)
            return record_run_heartbeat(conn, run_id, stage=body.stage)
        except RunNotFound as exc:
            raise HTTPException(status_code=404, detail="cloud run not found") from exc

    @app.post("/api/cloud/runs/{run_id}/cancel")
    def cancel_cloud_run(
        run_id: str, body: CloudCancelRequest, http_request: Request
    ):
        try:
            _get_cloud_run(conn, run_id, http_request)
            return cancel_run(conn, run_id, reason=body.reason)
        except RunNotFound as exc:
            raise HTTPException(status_code=404, detail="cloud run not found") from exc

    @app.post("/api/cloud/runs/{run_id}/sources/evaluate")
    def evaluate_cloud_run_source(
        run_id: str, body: CloudSourceEvaluationRequest, http_request: Request
    ):
        try:
            _get_cloud_run(conn, run_id, http_request)
            return evaluate_source_for_run(conn, run_id, body.url)
        except RunNotFound as exc:
            raise HTTPException(status_code=404, detail="cloud run not found") from exc

    @app.post("/api/cloud/runs/{run_id}/application-packets/prepared")
    def record_cloud_run_prepared_packet(
        run_id: str, body: CloudPreparedPacketRequest, http_request: Request
    ):
        try:
            _get_cloud_run(conn, run_id, http_request)
            return record_prepared_packet(conn, run_id, body.packet_manifest)
        except RunNotFound as exc:
            raise HTTPException(status_code=404, detail="cloud run not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/cloud/runs/{run_id}/final-submit")
    def cloud_run_final_submit(
        run_id: str, body: CloudFinalSubmitRequest, http_request: Request
    ):
        try:
            _get_cloud_run(conn, run_id, http_request)
            return create_manual_final_submit_instruction(
                conn,
                run_id,
                packet_id=body.packet_id,
                apply_url=body.apply_url,
                requested_by_automation=body.requested_by_automation,
            )
        except RunNotFound as exc:
            raise HTTPException(status_code=404, detail="cloud run not found") from exc
        except ManualFinalSubmitBlocked as exc:
            raise HTTPException(status_code=409, detail=exc.instruction) from exc

    app.include_router(
        create_api_v1_router(
            conn=conn,
            get_adapter_registry=lambda: app.state.adapter_registry,
            get_fit_gate_client=lambda: app.state.fit_gate_client,
            filter_companies_by_decision=_filter_companies_by_decision,
            filter_companies_by_connections=_filter_companies_by_connections,
            sort_companies_by_connections=_sort_companies_by_connections,
            dashboard_decision_filter=_dashboard_decision_filter,
            dashboard_connection_filter=_dashboard_connection_filter,
            profile_summary=_profile_summary,
            latest_succeeded_run_finished_at=_latest_succeeded_run_finished_at,
            job_detail=_job_detail,
            unreviewed_job_rows=_unreviewed_job_rows,
            resume_sections_for_profile=_resume_sections_for_profile,
            resume_suggestions_for_profile=_resume_suggestions_for_profile,
            application_packet_for_job=_application_packet_for_job,
            referral_contacts_for_job=_referral_contacts_for_job,
            prepare_application_packet=_prepare_application_packet,
            add_referral_contact=_add_referral_contact,
            company_id_for_job=_company_id_for_job,
            referral_contacts_by_job_id=_referral_contacts_by_job_id,
            source_health_rows=_source_health_rows,
            source_review_rows=_source_review_rows,
            source_support_summary=_source_support_summary,
            resume_asset_dir=app.state.resume_asset_dir,
            db_path=app.state.db_path,
            get_vision_fallback_provider=lambda: app.state.vision_fallback_provider,
            get_resume_rewrite_client=lambda: app.state.resume_rewrite_client,
            resume_section=_resume_section,
            update_resume_suggestion_status=_update_resume_suggestion_status,
            review_company_source=review_company_source,
            refresh_source=refresh_source,
            get_authenticated_user_id=_authenticated_user_id,
        )
    )

    return app


def create_app_from_env() -> FastAPI:
    paths = hosted_paths_from_env()
    ensure_hosted_directories(paths)
    os.environ.setdefault("ML_JOB_SWARM_DB_PATH", paths["db_path"])
    os.environ.setdefault("ML_JOB_SWARM_RESUME_ASSET_DIR", paths["resume_asset_dir"])
    app = create_app(paths["db_path"])
    seed_path = Path(
        os.environ.get("ML_JOB_SWARM_SEED_COMPANIES", str(DEFAULT_SEED_COMPANIES_PATH))
    )
    imported = 0
    if seed_path.exists():
        imported = import_seed_companies(app.state.conn, seed_path)
    app.state.seed_companies_path = str(seed_path)
    app.state.seed_companies_imported = imported
    catalog_import_path = os.environ.get("ML_JOB_SWARM_IMPORT_CATALOG_FROM", "").strip()
    if catalog_import_path:
        from ml_job_swarm.catalog_import import import_job_catalog

        app.state.catalog_import_summary = import_job_catalog(
            app.state.conn,
            Path(catalog_import_path),
        )
    return app


def _authenticated_user_id(request: Request) -> str | None:
    return getattr(request.state, "user_id", None)


def _resolve_cloud_user_id(request: Request, requested_user_id: str | None) -> str:
    auth_user_id = _authenticated_user_id(request)
    if auth_user_id:
        if requested_user_id and requested_user_id != auth_user_id:
            raise HTTPException(status_code=403, detail="user_id mismatch")
        return auth_user_id
    if not requested_user_id:
        raise HTTPException(status_code=400, detail="user_id is required")
    return requested_user_id


def _get_cloud_run(conn, run_id: str, request: Request) -> dict[str, object]:
    auth_user_id = _authenticated_user_id(request)
    if auth_user_id:
        return get_run_for_user(conn, run_id, user_id=auth_user_id)
    return get_run(conn, run_id)


def _require_profile_access(request: Request, target_profile_id: int) -> None:
    try:
        require_target_profile_access(
            request.app.state.conn,
            target_profile_id,
            user_id=_authenticated_user_id(request),
        )
    except ProfileAccessDenied as exc:
        raise HTTPException(status_code=403, detail="target profile not accessible") from exc


def _render(
    request: Request,
    template_name: str,
    *,
    status_code: int = 200,
    **context: object,
) -> HTMLResponse:
    template = request.app.state.templates.get_template(template_name)
    context.setdefault("deployment_status", request.app.state.deployment_status)
    context.setdefault(
        "storage_label",
        "Hosted on Railway" if is_hosted_deployment() else "SQLite local",
    )
    return HTMLResponse(
        template.render(request=request, **context),
        status_code=status_code,
    )


def _deployment_status_from_env(env: Mapping[str, str]) -> dict[str, str]:
    explicit_url = (env.get("ML_JOB_SWARM_PUBLIC_URL") or env.get("PUBLIC_URL") or "").strip()
    if explicit_url:
        return {
            "label": "Public URL configured",
            "detail": "Runtime points at an explicitly configured public URL.",
            "url": _normalise_public_url(explicit_url),
            "source": "ML_JOB_SWARM_PUBLIC_URL" if env.get("ML_JOB_SWARM_PUBLIC_URL") else "PUBLIC_URL",
        }

    for key in ("RENDER_EXTERNAL_URL", "VERCEL_URL", "RAILWAY_PUBLIC_DOMAIN"):
        value = (env.get(key) or "").strip()
        if value:
            return {
                "label": "Public URL configured",
                "detail": f"Runtime detected {key}.",
                "url": _normalise_public_url(value),
                "source": key,
            }

    fly_app = (env.get("FLY_APP_NAME") or "").strip()
    if fly_app:
        return {
            "label": "Public URL configured",
            "detail": "Runtime detected FLY_APP_NAME.",
            "url": f"https://{fly_app}.fly.dev",
            "source": "FLY_APP_NAME",
        }

    return {
        "label": "Local development",
        "detail": "No public URL configured",
        "url": "",
        "source": "local",
    }


def _normalise_public_url(value: str) -> str:
    if value.startswith(("http://", "https://")):
        return value.rstrip("/")
    return f"https://{value.rstrip('/')}"


def _require_supported_resume(resume: UploadFile) -> None:
    suffix = Path(resume.filename or "").suffix.casefold()
    allowed_suffixes = set(SUPPORTED_RESUME_TYPES.values())
    if resume.content_type in SUPPORTED_RESUME_TYPES and suffix in allowed_suffixes:
        return
    raise HTTPException(status_code=400, detail="Resume must be a PDF or DOCX file")


def _resume_sections_for_profile(conn, target_profile_id: int) -> list[dict[str, object]]:
    rows = conn.execute(
        """
        SELECT
          resume_sections.id,
          resume_sections.section_type,
          resume_sections.heading,
          resume_sections.text
        FROM target_profiles
        JOIN resume_parse_runs
          ON resume_parse_runs.resume_asset_id = target_profiles.resume_asset_id
        JOIN resume_sections
          ON resume_sections.parse_run_id = resume_parse_runs.id
        WHERE target_profiles.id = ?
        ORDER BY resume_parse_runs.id DESC, resume_sections.sort_order, resume_sections.id
        """,
        (target_profile_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def _profile_summary(conn, target_profile_id: int) -> dict[str, object]:
    row = conn.execute(
        """
        SELECT
          target_profiles.id,
          target_profiles.name,
          target_profiles.version,
          target_profiles.desired_titles_json,
          target_profiles.levels_json,
          target_profiles.locations_json,
          target_profiles.remote_modes_json,
          target_profiles.company_stages_json,
          resume_assets.original_filename
        FROM target_profiles
        LEFT JOIN resume_assets
          ON resume_assets.id = target_profiles.resume_asset_id
        WHERE target_profiles.id = ?
        """,
        (target_profile_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"target_profile_id not found: {target_profile_id}")

    keyword_rows = conn.execute(
        """
        SELECT resume_keywords.keyword
        FROM target_profiles
        JOIN resume_parse_runs
          ON resume_parse_runs.resume_asset_id = target_profiles.resume_asset_id
        JOIN resume_keywords
          ON resume_keywords.parse_run_id = resume_parse_runs.id
        WHERE target_profiles.id = ?
          AND resume_parse_runs.id = (
            SELECT MAX(latest_runs.id)
            FROM resume_parse_runs AS latest_runs
            WHERE latest_runs.resume_asset_id = target_profiles.resume_asset_id
          )
        ORDER BY resume_keywords.weight DESC, resume_keywords.id
        LIMIT 12
        """,
        (target_profile_id,),
    ).fetchall()

    return {
        "id": row["id"],
        "name": row["name"],
        "version": row["version"],
        "resume_filename": row["original_filename"] or "",
        "desired_titles": _safe_json_list(row["desired_titles_json"]),
        "levels": _safe_json_list(row["levels_json"]),
        "locations": _safe_json_list(row["locations_json"]),
        "remote_modes": _safe_json_list(row["remote_modes_json"]),
        "company_stages": _safe_json_list(row["company_stages_json"]),
        "keywords": [keyword_row["keyword"] for keyword_row in keyword_rows],
    }


def _resume_section(conn, section_id: int):
    return conn.execute(
        """
        SELECT
          resume_sections.id,
          resume_sections.section_type,
          resume_sections.heading,
          resume_sections.text,
          resume_parse_runs.resume_asset_id
        FROM resume_sections
        JOIN resume_parse_runs
          ON resume_parse_runs.id = resume_sections.parse_run_id
        WHERE resume_sections.id = ?
        """,
        (section_id,),
    ).fetchone()


def _resume_suggestions_for_profile(
    conn, target_profile_id: int
) -> list[dict[str, object]]:
    rows = conn.execute(
        """
        SELECT
          resume_rewrite_suggestions.id,
          resume_rewrite_suggestions.section_id,
          resume_rewrite_suggestions.suggestion_text,
          resume_rewrite_suggestions.status,
          resume_rewrite_suggestions.created_at,
          resume_sections.heading,
          resume_sections.section_type
        FROM resume_rewrite_suggestions
        LEFT JOIN resume_sections
          ON resume_sections.id = resume_rewrite_suggestions.section_id
        WHERE resume_rewrite_suggestions.target_profile_id = ?
        ORDER BY resume_rewrite_suggestions.id DESC
        """,
        (target_profile_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def _update_resume_suggestion_status(
    conn, suggestion_id: int, status: str, target_profile_id: int | None
) -> bool:
    row = conn.execute(
        """
        SELECT target_profile_id, status
        FROM resume_rewrite_suggestions
        WHERE id = ?
        """,
        (suggestion_id,),
    ).fetchone()
    if row is None:
        return False
    if target_profile_id is not None and row["target_profile_id"] != target_profile_id:
        return False
    if row["status"] == "draft":
        conn.execute(
            """
            UPDATE resume_rewrite_suggestions
            SET status = ?
            WHERE id = ?
            """,
            (status, suggestion_id),
        )
        conn.commit()
    return True


def _source_review_rows(
    conn,
    supported_source_types: set[str] | None = None,
) -> list[dict[str, object]]:
    rows = conn.execute(
        """
        SELECT
          id,
          company_name,
          requested_url,
          reason,
          status,
          reviewed_at,
          reviewed_by,
          created_at
        FROM company_source_review_queue
        ORDER BY
          CASE status
            WHEN 'pending' THEN 0
            WHEN 'blocked' THEN 1
            WHEN 'rejected' THEN 2
            WHEN 'approved' THEN 3
            ELSE 4
          END,
          id DESC
        """
    ).fetchall()
    return [
        _source_review_row_with_preflight(dict(row), supported_source_types or set())
        for row in rows
    ]


def _source_review_row_with_preflight(
    row: dict[str, object],
    supported_source_types: set[str],
) -> dict[str, object]:
    requested_url = str(row.get("requested_url") or "")
    policy = classify_source_url(requested_url)
    normalized_url = policy.normalized_url or requested_url
    source_type = infer_source_type(normalized_url)
    if policy.mode == "blocked":
        adapter_status = "blocked"
        adapter_status_label = "Blocked by policy"
    elif policy.mode != "allowed":
        adapter_status = "manual_only"
        adapter_status_label = "Not refreshable"
    elif source_type in supported_source_types:
        adapter_status = "ready"
        adapter_status_label = "Ready"
    else:
        adapter_status = "unsupported"
        adapter_status_label = "No adapter"
    return row | {
        "policy_mode": policy.mode,
        "policy_reason": policy.reason,
        "policy_label": f"{policy.mode}:{policy.reason}",
        "inferred_source_type": source_type,
        "adapter_status": adapter_status,
        "adapter_status_label": adapter_status_label,
    }


def _source_intake_preview(
    company_name: str,
    source_url: str,
    supported_source_types: set[str],
) -> dict[str, object] | None:
    if not company_name or not source_url:
        return None
    policy = classify_source_url(source_url)
    normalized_url = policy.normalized_url or source_url
    source_type = infer_source_type(normalized_url)
    if policy.mode == "blocked":
        support_status = "blocked"
        support_label = "Cannot queue restricted source"
        can_queue = False
    elif policy.mode != "allowed":
        support_status = "manual_only"
        support_label = "Not refreshable yet"
        can_queue = True
    elif source_type in supported_source_types:
        support_status = "ready"
        support_label = "Ready to refresh after review"
        can_queue = True
    else:
        support_status = "unsupported"
        support_label = "No adapter yet"
        can_queue = True
    return {
        "company_name": company_name,
        "source_url": source_url,
        "normalized_url": normalized_url,
        "policy_label": f"{policy.mode}:{policy.reason}",
        "inferred_source_type": source_type,
        "support_status": support_status,
        "support_label": support_label,
        "can_queue": can_queue,
    }


def _admin_audit_rows(conn) -> list[dict[str, object]]:
    rows = conn.execute(
        """
        SELECT
          id,
          actor,
          action,
          target_type,
          target_id,
          before_json,
          after_json,
          created_at
        FROM admin_audit_events
        ORDER BY id DESC
        """
    ).fetchall()
    audit_events = []
    for row in rows:
        before = _sanitize_details(_safe_json_object(row["before_json"]))
        after = _sanitize_details(_safe_json_object(row["after_json"]))
        audit_events.append(
            {
                "id": row["id"],
                "actor": row["actor"],
                "action": row["action"],
                "target_type": row["target_type"],
                "target_id": row["target_id"],
                "before_json": json.dumps(before, sort_keys=True),
                "after_json": json.dumps(after, sort_keys=True),
                "created_at": row["created_at"],
            }
        )
    return audit_events


def _ingestion_run_rows(conn) -> list[dict[str, object]]:
    rows = conn.execute(
        """
        SELECT
          id,
          started_at,
          finished_at,
          status,
          source_count,
          jobs_seen,
          jobs_added,
          jobs_updated,
          jobs_closed,
          error
        FROM ingestion_runs
        ORDER BY id DESC
        LIMIT 100
        """
    ).fetchall()
    return [
        {
            **dict(row),
            "error": _sanitize_error_text(row["error"]),
        }
        for row in rows
    ]


def _ingestion_run_detail(conn, run_id: int) -> dict[str, object] | None:
    row = conn.execute(
        """
        SELECT
          id,
          started_at,
          finished_at,
          status,
          source_count,
          jobs_seen,
          jobs_added,
          jobs_updated,
          jobs_closed,
          error
        FROM ingestion_runs
        WHERE id = ?
        """,
        (run_id,),
    ).fetchone()
    if row is None:
        return None
    snapshot_count = conn.execute(
        "SELECT COUNT(*) FROM job_snapshots WHERE ingestion_run_id = ?",
        (run_id,),
    ).fetchone()[0]
    return {
        **dict(row),
        "error": _sanitize_error_text(row["error"]),
        "snapshot_count": int(snapshot_count),
        "snapshot_limit": 250,
    }


def _run_friction_rows(conn, run_id: int) -> list[dict[str, object]]:
    rows = conn.execute(
        """
        SELECT
          source_friction_events.id,
          companies.name AS company,
          source_friction_events.url AS source_url,
          source_friction_events.event_type,
          source_friction_events.status_code,
          source_friction_events.details_json,
          source_friction_events.review_status,
          source_friction_events.created_at
        FROM source_friction_events
        LEFT JOIN job_sources
          ON job_sources.id = source_friction_events.job_source_id
        LEFT JOIN companies
          ON companies.id = job_sources.company_id
        WHERE source_friction_events.ingestion_run_id = ?
        ORDER BY source_friction_events.id
        """,
        (run_id,),
    ).fetchall()
    friction_rows = []
    for row in rows:
        details = _sanitize_details(_safe_json_object(row["details_json"]))
        friction_rows.append(
            {
                **dict(row),
                "company": row["company"] or "Unknown",
                "status_code": row["status_code"] or "",
                "details_json": json.dumps(details, sort_keys=True),
            }
        )
    return friction_rows


def _run_snapshot_rows(conn, run_id: int) -> list[dict[str, object]]:
    rows = conn.execute(
        """
        SELECT
          job_snapshots.id,
          job_snapshots.external_id,
          job_snapshots.title,
          job_snapshots.company_name,
          job_snapshots.location_text,
          job_snapshots.remote_mode,
          job_snapshots.captured_at,
          job_sources.url AS source_url
        FROM job_snapshots
        LEFT JOIN job_sources
          ON job_sources.id = job_snapshots.job_source_id
        WHERE job_snapshots.ingestion_run_id = ?
        ORDER BY job_snapshots.id
        LIMIT 250
        """,
        (run_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def _admin_runs_summary_redirect(
    *,
    refresh_status: str,
    sources_seen: int,
    sources_attempted: int,
    sources_succeeded: int,
    sources_refreshed: int,
    sources_skipped: int,
    jobs_seen: int,
    jobs_closed: int,
    suspicious_empty: int,
    failures: int,
    blocked: int,
) -> RedirectResponse:
    params = urlencode(
        {
            "refresh_status": refresh_status,
            "sources_seen": sources_seen,
            "sources_attempted": sources_attempted,
            "sources_succeeded": sources_succeeded,
            "sources_refreshed": sources_refreshed,
            "sources_skipped": sources_skipped,
            "jobs_seen": jobs_seen,
            "jobs_closed": jobs_closed,
            "suspicious_empty": suspicious_empty,
            "failures": failures,
            "blocked": blocked,
        }
    )
    return RedirectResponse(f"/admin/runs?{params}", status_code=303)


def _reviewed_source_count(conn, source_types: set[str] | None = None) -> int:
    if source_types is None:
        row = conn.execute(
            """
            SELECT COUNT(*)
            FROM job_sources
            WHERE disabled_at IS NULL AND review_status = 'reviewed'
            """
        ).fetchone()
        return int(row[0])
    if not source_types:
        return 0
    placeholders = ", ".join("?" for _ in source_types)
    row = conn.execute(
        f"""
        SELECT COUNT(*)
        FROM job_sources
        WHERE disabled_at IS NULL
          AND review_status = 'reviewed'
          AND source_type IN ({placeholders})
        """,
        sorted(source_types),
    ).fetchone()
    return int(row[0])


def _source_health_rows(
    conn,
    supported_source_types: set[str] | None = None,
) -> list[dict[str, object]]:
    rows = conn.execute(
        """
        SELECT
          job_sources.id,
          companies.name AS company_name,
          job_sources.url,
          job_sources.source_type,
          job_sources.policy_mode,
          job_sources.review_status,
          job_sources.disabled_at,
          job_sources.last_checked_at,
          job_sources.company_id,
          (
            SELECT COUNT(*)
            FROM jobs
            WHERE jobs.job_source_id = job_sources.id AND jobs.status = 'open'
          ) AS active_job_count,
          (
            SELECT COUNT(*)
            FROM jobs
            WHERE jobs.company_id = job_sources.company_id AND jobs.status = 'open'
          ) AS company_open_job_count,
          (
            SELECT event_type
            FROM source_friction_events
            WHERE source_friction_events.job_source_id = job_sources.id
            ORDER BY id DESC
            LIMIT 1
          ) AS latest_event_type,
          (
            SELECT details_json
            FROM source_friction_events
            WHERE source_friction_events.job_source_id = job_sources.id
            ORDER BY id DESC
            LIMIT 1
          ) AS latest_details_json,
          (
            SELECT created_at
            FROM source_friction_events
            WHERE source_friction_events.job_source_id = job_sources.id
            ORDER BY id DESC
            LIMIT 1
          ) AS latest_event_created_at
        FROM job_sources
        JOIN companies ON companies.id = job_sources.company_id
        ORDER BY companies.name, job_sources.url
        """
    ).fetchall()
    supported_source_types = supported_source_types or set()
    sources = []
    for row in rows:
        latest_details = _safe_json_object(row["latest_details_json"])
        adapter_status, adapter_status_label = _adapter_status(
            row["source_type"],
            row["disabled_at"],
            supported_source_types,
        )
        latest_event_type = row["latest_event_type"]
        if _source_has_recovered_from_friction(row):
            latest_event_type = None
            latest_details = {}
        health_status, health_status_label = _source_health_status(
            row,
            adapter_status,
            latest_event_type,
        )
        sources.append(
            {
                **dict(row),
                "latest_event_type": latest_event_type,
                "adapter_status": adapter_status,
                "adapter_status_label": adapter_status_label,
                "health_status": health_status,
                "health_status_label": health_status_label,
                "latest_recommendation": latest_details.get(
                    "recommendation", "manual review" if latest_event_type else "healthy"
                ),
            }
        )
    return sources


def _source_has_recovered_from_friction(row) -> bool:
    if not row["latest_event_type"] or not row["latest_event_created_at"]:
        return False
    if not row["last_checked_at"]:
        return False
    if int(row["active_job_count"] or 0) <= 0:
        return False
    return _timestamp_sort_key(row["last_checked_at"]) > _timestamp_sort_key(
        row["latest_event_created_at"]
    )


def _timestamp_sort_key(value: object) -> str:
    return str(value or "").replace("T", " ")


def _source_health_status(
    row,
    adapter_status: str,
    latest_event_type: object,
) -> tuple[str, str]:
    if row["disabled_at"] is not None:
        return "disabled", "Disabled"
    if adapter_status == "unsupported":
        return "unsupported", "No adapter"
    if latest_event_type in {"empty_suspicious", "manual_review_needed"}:
        company_jobs = int(row["company_open_job_count"] or 0)
        if row["source_type"] == "careers" and company_jobs > 0:
            return "covered", "Covered by ATS source"
        if (
            latest_event_type == "empty_suspicious"
            and row["source_type"] == "careers"
        ):
            return "spa-fallback", "SPA careers page"
    if latest_event_type:
        return "needs-review", "Needs review"
    if not row["last_checked_at"]:
        return "unchecked", "Unchecked"
    return "healthy", "Healthy"


def _source_support_summary(sources: list[dict[str, object]]) -> dict[str, int]:
    return {
        "total": len(sources),
        "ready": sum(1 for source in sources if source["adapter_status"] == "ready"),
        "unsupported": sum(
            1 for source in sources if source["adapter_status"] == "unsupported"
        ),
        "disabled": sum(
            1 for source in sources if source["adapter_status"] == "disabled"
        ),
    }


def _adapter_status(
    source_type: str,
    disabled_at: object,
    supported_source_types: set[str],
) -> tuple[str, str]:
    if disabled_at is not None:
        return "disabled", "Disabled"
    if source_type in supported_source_types:
        return "ready", "Adapter ready"
    return "unsupported", "No adapter"


def _job_detail(conn, job_id: int, target_profile_id: int) -> dict[str, object] | None:
    profile_version = current_profile_version(conn, target_profile_id)
    row = conn.execute(
        """
        SELECT
          jobs.id,
          jobs.title,
          jobs.department,
          jobs.location_text,
          jobs.remote_mode,
          jobs.employment_type,
          jobs.seniority,
          jobs.description_text,
          jobs.requirements_text,
          jobs.apply_url,
          jobs.source_url,
          jobs.status,
          companies.name AS company_name,
          fit_reviews.fit_score,
          fit_reviews.label,
          fit_reviews.reasons_json,
          fit_reviews.risks_json,
          fit_reviews.recommendation,
          job_decisions.decision,
          COALESCE(job_decisions.notes, '') AS notes
        FROM jobs
        JOIN companies ON companies.id = jobs.company_id
        LEFT JOIN fit_reviews
          ON fit_reviews.id = (
            SELECT MAX(id)
            FROM fit_reviews
            WHERE job_id = jobs.id
              AND target_profile_id = ?
              AND profile_version = ?
          )
        LEFT JOIN job_decisions
          ON job_decisions.job_id = jobs.id
         AND job_decisions.target_profile_id = ?
        WHERE jobs.id = ?
        """,
        (target_profile_id, profile_version, target_profile_id, job_id),
    ).fetchone()
    if row is None:
        return None
    detail = dict(row)
    detail["reasons"] = _safe_json_list(row["reasons_json"])
    detail["risks"] = _safe_json_list(row["risks_json"])
    return detail


def _unreviewed_job_rows(
    conn,
    target_profile_id: int,
    *,
    limit: int = 12,
) -> list[dict[str, object]]:
    profile_version = current_profile_version(conn, target_profile_id)
    rows = conn.execute(
        """
        SELECT
          jobs.id AS job_id,
          jobs.title,
          jobs.location_text,
          jobs.remote_mode,
          companies.name AS company_name
        FROM jobs
        JOIN companies ON companies.id = jobs.company_id
        WHERE jobs.status = 'open'
          AND NOT EXISTS (
            SELECT 1
            FROM fit_reviews
            WHERE fit_reviews.job_id = jobs.id
              AND fit_reviews.target_profile_id = ?
              AND fit_reviews.profile_version = ?
          )
        ORDER BY jobs.last_seen_at DESC, jobs.id DESC
        LIMIT ?
        """,
        (target_profile_id, profile_version, limit),
    ).fetchall()
    return [dict(row) for row in rows]


def _prepare_application_packet(
    conn,
    *,
    job_id: int,
    target_profile_id: int,
) -> int:
    detail = _job_detail(conn, job_id, target_profile_id)
    if detail is None:
        raise ValueError("Job not found")

    packet = _application_packet_payload(
        detail,
        accepted_resume_rewrites=_accepted_resume_rewrites(conn, target_profile_id),
    )
    checklist = _application_checklist(detail)
    manual_submit_url = str(detail.get("apply_url") or "")
    with conn:
        conn.execute(
            """
            INSERT INTO application_packets (
              job_id,
              target_profile_id,
              status,
              packet_json,
              checklist_json,
              manual_submit_url,
              updated_at
            )
            VALUES (?, ?, 'prepared', ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(job_id, target_profile_id) DO UPDATE SET
              status = CASE
                WHEN application_packets.status = 'submitted' THEN 'submitted'
                ELSE 'prepared'
              END,
              packet_json = excluded.packet_json,
              checklist_json = excluded.checklist_json,
              manual_submit_url = excluded.manual_submit_url,
              updated_at = CURRENT_TIMESTAMP
            """,
            (
                job_id,
                target_profile_id,
                json.dumps(packet, sort_keys=True),
                json.dumps(checklist, sort_keys=True),
                manual_submit_url,
            ),
        )
    row = conn.execute(
        """
        SELECT id
        FROM application_packets
        WHERE job_id = ?
          AND target_profile_id = ?
        """,
        (job_id, target_profile_id),
    ).fetchone()
    return int(row["id"])


def _company_id_for_job(conn, job_id: int) -> int | None:
    row = conn.execute("SELECT company_id FROM jobs WHERE id = ?", (job_id,)).fetchone()
    return int(row["company_id"]) if row else None


def _accepted_resume_rewrites(
    conn,
    target_profile_id: int,
) -> list[dict[str, object]]:
    rows = conn.execute(
        """
        SELECT
          resume_rewrite_suggestions.section_id,
          COALESCE(resume_sections.section_type, '') AS section_type,
          COALESCE(resume_sections.heading, '') AS heading,
          resume_rewrite_suggestions.suggestion_text
        FROM resume_rewrite_suggestions
        LEFT JOIN resume_sections
          ON resume_sections.id = resume_rewrite_suggestions.section_id
        WHERE resume_rewrite_suggestions.target_profile_id = ?
          AND resume_rewrite_suggestions.status = 'accepted'
        ORDER BY resume_rewrite_suggestions.id DESC
        """,
        (target_profile_id,),
    ).fetchall()
    return [
        {
            "section_id": row["section_id"],
            "section_type": row["section_type"],
            "heading": row["heading"],
            "suggestion_text": row["suggestion_text"],
        }
        for row in rows
    ]


def _add_referral_contact(
    conn,
    *,
    company_id: int,
    name: str,
    email: str,
    title: str,
    relationship: str,
    notes: str,
) -> int:
    with conn:
        cursor = conn.execute(
            """
            INSERT INTO contacts (name, email, title, notes)
            VALUES (?, ?, ?, ?)
            """,
            (name, email, title, notes),
        )
        contact_id = int(cursor.lastrowid)
        conn.execute(
            """
            INSERT INTO referral_contacts (
              company_id,
              contact_id,
              relationship
            )
            VALUES (?, ?, ?)
            """,
            (company_id, contact_id, relationship),
        )
    return contact_id


def _referral_contacts_for_job(conn, *, job_id: int) -> list[dict[str, object]]:
    rows = conn.execute(
        """
        SELECT
          contacts.id,
          contacts.name,
          contacts.email,
          contacts.title,
          contacts.notes,
          referral_contacts.relationship
        FROM jobs
        JOIN referral_contacts
          ON referral_contacts.company_id = jobs.company_id
        JOIN contacts
          ON contacts.id = referral_contacts.contact_id
        WHERE jobs.id = ?
        ORDER BY contacts.name, contacts.id
        """,
        (job_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def _referral_contacts_by_job_id(
    conn,
    job_ids: list[int],
) -> dict[int, list[dict[str, object]]]:
    if not job_ids:
        return {}
    placeholders = ",".join("?" for _ in job_ids)
    rows = conn.execute(
        f"""
        SELECT
          jobs.id AS job_id,
          contacts.id,
          contacts.name,
          contacts.email,
          contacts.title,
          contacts.notes,
          referral_contacts.relationship
        FROM jobs
        JOIN referral_contacts
          ON referral_contacts.company_id = jobs.company_id
        JOIN contacts
          ON contacts.id = referral_contacts.contact_id
        WHERE jobs.id IN ({placeholders})
        ORDER BY jobs.id, contacts.name, contacts.id
        """,
        tuple(job_ids),
    ).fetchall()
    grouped: dict[int, list[dict[str, object]]] = {}
    for row in rows:
        item = dict(row)
        job_id = int(item.pop("job_id"))
        grouped.setdefault(job_id, []).append(item)
    return grouped


def _application_packet_for_job(
    conn,
    *,
    job_id: int,
    target_profile_id: int,
) -> dict[str, object] | None:
    row = conn.execute(
        """
        SELECT *
        FROM application_packets
        WHERE job_id = ?
          AND target_profile_id = ?
        """,
        (job_id, target_profile_id),
    ).fetchone()
    if row is None:
        return None
    packet = dict(row)
    packet["packet"] = _safe_json_object(row["packet_json"])
    packet["checklist"] = _safe_json_list(row["checklist_json"])
    return packet


def _application_packet_payload(
    detail: dict[str, object],
    *,
    accepted_resume_rewrites: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    return {
        "company": detail.get("company_name") or "",
        "title": detail.get("title") or "",
        "apply_url": detail.get("apply_url") or "",
        "source_url": detail.get("source_url") or "",
        "fit_score": detail.get("fit_score"),
        "label": detail.get("label") or "",
        "recommendation": detail.get("recommendation") or "",
        "reasons": detail.get("reasons") or [],
        "risks": detail.get("risks") or [],
        "notes": detail.get("notes") or "",
        "accepted_resume_rewrites": accepted_resume_rewrites or [],
    }


def _application_checklist(detail: dict[str, object]) -> list[dict[str, object]]:
    return [
        {
            "id": "review_fit",
            "label": "Review fit reasons and mismatch risks",
            "done": False,
        },
        {
            "id": "review_resume",
            "label": "Review resume suggestions before applying",
            "done": False,
        },
        {
            "id": "manual_submit",
            "label": "Open the apply page and complete manual final submit",
            "done": False,
            "url": detail.get("apply_url") or "",
        },
        {
            "id": "record_status",
            "label": "Return here and mark submitted after manual final submit",
            "done": False,
        },
    ]


def _friction_export_rows(conn) -> list[dict[str, object]]:
    rows = conn.execute(
        """
        SELECT
          source_friction_events.id,
          companies.name AS company,
          source_friction_events.url AS source_url,
          source_friction_events.event_type,
          source_friction_events.status_code,
          source_friction_events.details_json,
          source_friction_events.review_status,
          source_friction_events.reviewed_at,
          source_friction_events.reviewed_by,
          source_friction_events.review_note,
          source_friction_events.created_at
        FROM source_friction_events
        LEFT JOIN job_sources
          ON job_sources.id = source_friction_events.job_source_id
        LEFT JOIN companies
          ON companies.id = job_sources.company_id
        ORDER BY source_friction_events.id
        """
    ).fetchall()
    export_rows = []
    for row in rows:
        details = _sanitize_details(_safe_json_object(row["details_json"]))
        export_rows.append(
            {
                "id": row["id"],
                "company": row["company"] or "",
                "source_url": row["source_url"],
                "event_type": row["event_type"],
                "status_code": row["status_code"] or "",
                "details_json": json.dumps(details, sort_keys=True),
                "review_status": row["review_status"],
                "reviewed_at": row["reviewed_at"] or "",
                "reviewed_by": row["reviewed_by"] or "",
                "review_note": _sanitize_review_note(row["review_note"]),
                "created_at": row["created_at"],
            }
        )
    return export_rows


def _dashboard_decision_filter(value: str) -> str:
    return value if value in {"all", "saved", "unmarked", "hidden"} else "all"


def _dashboard_connection_filter(value: str) -> str:
    return value if value in {"all", "with_connections"} else "all"


def _filter_companies_by_connections(
    companies: list[CompanyResult],
    connections_by_company_id: dict[int, list[dict[str, object]]],
    connection_filter: str,
) -> list[CompanyResult]:
    if connection_filter != "with_connections":
        return companies
    return [
        company
        for company in companies
        if connections_by_company_id.get(company.company_id)
    ]


def _sort_companies_by_connections(
    companies: list[CompanyResult],
    connections_by_company_id: dict[int, list[dict[str, object]]],
) -> list[CompanyResult]:
    return sorted(
        companies,
        key=lambda company: (
            0 if connections_by_company_id.get(company.company_id) else 1,
            -len(connections_by_company_id.get(company.company_id, [])),
            company.name.casefold(),
        ),
    )


def _linkedin_connections_for_job(
    conn,
    *,
    job_id: int,
    user_id: str | None = None,
) -> list[dict[str, object]]:
    company_id = _company_id_for_job(conn, job_id)
    if company_id is None:
        return []
    return connections_for_company_id(conn, company_id, user_id=user_id)


def _filter_companies_by_decision(
    companies: list[CompanyResult], decision_filter: str
) -> list[CompanyResult]:
    if decision_filter == "all":
        return companies

    filtered_companies: list[CompanyResult] = []
    for company in companies:
        jobs = _jobs_matching_decision_filter(company, decision_filter)
        if not jobs:
            continue
        filtered_companies.append(
            CompanyResult(
                company_id=company.company_id,
                name=company.name,
                visible_jobs=jobs,
                mismatch_risk_jobs=[],
                hidden_jobs=[],
                filtered_out_count=0,
            )
        )
    return filtered_companies


def _jobs_matching_decision_filter(
    company: CompanyResult, decision_filter: str
) -> list[JobFitResult]:
    jobs = [
        *company.visible_jobs,
        *company.mismatch_risk_jobs,
        *company.hidden_jobs,
    ]
    if decision_filter == "saved":
        return [job for job in jobs if job.decision == "saved"]
    if decision_filter == "hidden":
        return [job for job in jobs if job.decision == "hidden"]
    return [job for job in jobs if job.decision is None]


def _csv_safe_row(row: dict[str, object]) -> dict[str, object]:
    return {key: _csv_safe_value(value) for key, value in row.items()}


def _csv_safe_value(value: object) -> object:
    if not isinstance(value, str):
        return value
    stripped = value.lstrip()
    if stripped.startswith(("=", "+", "-", "@")):
        return f"'{value}"
    return value


def _filter_saved_jobs(
    rows: list[dict[str, object]], query: str
) -> list[dict[str, object]]:
    if not query:
        return rows
    needle = query.casefold()
    fields = ("company", "title", "recommendation", "notes")
    return [
        row
        for row in rows
        if any(needle in str(row.get(field, "")).casefold() for field in fields)
    ]


def _sort_saved_jobs(
    rows: list[dict[str, object]], sort_key: str
) -> list[dict[str, object]]:
    if sort_key == "score":
        return sorted(rows, key=lambda row: int(row.get("fit_score") or 0), reverse=True)
    if sort_key == "company":
        return sorted(
            rows,
            key=lambda row: (
                str(row.get("company") or "").casefold(),
                str(row.get("title") or "").casefold(),
            ),
        )
    if sort_key == "title":
        return sorted(
            rows,
            key=lambda row: (
                str(row.get("title") or "").casefold(),
                str(row.get("company") or "").casefold(),
            ),
        )
    return rows


def _safe_json_object(raw: object) -> dict[str, object]:
    if not raw:
        return {}
    try:
        parsed = json.loads(str(raw))
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _safe_json_list(raw: object) -> list[object]:
    if not raw:
        return []
    try:
        parsed = json.loads(str(raw))
    except json.JSONDecodeError:
        return []
    return parsed if isinstance(parsed, list) else []


def _latest_succeeded_run_finished_at(conn) -> str | None:
    row = conn.execute(
        "SELECT finished_at FROM ingestion_runs "
        "WHERE status = 'succeeded' AND finished_at IS NOT NULL "
        "ORDER BY id DESC LIMIT 1"
    ).fetchone()
    return row["finished_at"] if row else None


def _submitted_preferences(form) -> dict[str, str]:
    return {
        preference_id: str(form.get(preference_id, "")).strip()
        for preference_id in REQUIRED_PREFERENCE_IDS
    }


def _preferences_payload(submitted: dict[str, str]) -> dict[str, dict[str, str]]:
    return {
        preference_id: {"answer": submitted[preference_id]}
        for preference_id in REQUIRED_PREFERENCE_IDS
    }


def _safe_return_path(return_to: object, fallback: str) -> str:
    if not isinstance(return_to, str):
        return fallback
    if return_to.startswith("/") and not return_to.startswith("//"):
        return return_to
    return fallback


def _match_summary_from_query(query) -> dict[str, object] | None:
    run_label = "Match run"
    status = query.get("match_status")
    if status is None:
        run_label = "Source refresh"
        status = query.get("refresh_status")
    if status not in {"completed", "failed"}:
        return None
    return {
        "status": status,
        "run_label": run_label,
        "status_label": "completed" if status == "completed" else "completed with failures",
        "sources_attempted": _int_query_param(query, "sources_attempted"),
        "sources_succeeded": _int_query_param(query, "sources_succeeded"),
        "sources_refreshed": _int_query_param(query, "sources_refreshed"),
        "sources_skipped": _int_query_param(query, "sources_skipped"),
        "jobs_seen": _int_query_param(query, "jobs_seen"),
        "jobs_closed": _int_query_param(query, "jobs_closed"),
        "suspicious_empty": _int_query_param(query, "suspicious_empty"),
        "reviews_created": _int_query_param(query, "reviews_created"),
        "review_failures": _int_query_param(query, "review_failures"),
        "failures": _int_query_param(query, "failures"),
        "blocked": _int_query_param(query, "blocked"),
    }


def _int_query_param(query, key: str) -> int:
    try:
        return max(0, int(query.get(key, "0")))
    except (TypeError, ValueError):
        return 0


def _append_query_param(path: str, key: str, value: str) -> str:
    separator = "&" if "?" in path else "?"
    return f"{path}{separator}{key}={value}"


def _sanitize_review_note(note: object) -> str:
    if not note:
        return ""
    return _sanitize_error_text(str(note).strip())[:500]


def _sanitize_details(value: object) -> object:
    if isinstance(value, dict):
        return {
            key: _sanitize_details(item)
            for key, item in value.items()
            if not _is_sensitive_detail_key(key)
        }
    if isinstance(value, list):
        return [_sanitize_details(item) for item in value]
    if isinstance(value, str):
        return _sanitize_error_text(value)
    return value


def _is_sensitive_detail_key(key: str) -> bool:
    normalized_key = key.casefold()
    if normalized_key in SENSITIVE_DETAIL_KEYS:
        return True
    return any(term in normalized_key for term in SENSITIVE_DETAIL_KEY_TERMS)


def _sanitize_error_text(error: object) -> str:
    if not error:
        return ""
    text = str(error)
    normalized_text = text.casefold()
    if any(term in normalized_text for term in SENSITIVE_DETAIL_KEY_TERMS):
        return "[redacted]"
    return text[:500]
