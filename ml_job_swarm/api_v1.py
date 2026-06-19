from __future__ import annotations

import hashlib
import sqlite3
from collections.abc import Callable
from dataclasses import asdict, is_dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, ValidationError

from ml_job_swarm.ingest import refresh_due_sources, refresh_source
from ml_job_swarm.llm import (
    LLMRequest,
    ResumeRewriteResponse,
    VisionFallbackResponse,
    llm_usage_summary,
    record_llm_request,
    request_structured_response,
)
from ml_job_swarm.resume_assets import (
    ResumeAssetStorageError,
    load_resume_asset_bytes,
    pdf_page_image_content_parts,
    persist_resume_asset,
)

from ml_job_swarm.decisions import saved_job_export_rows
from ml_job_swarm.filtering import (
    CompanyResult,
    review_jobs_for_profile,
    review_jobs_for_profile_resilient,
    rules_preview_jobs,
    visible_company_results,
)
from ml_job_swarm.linkedin_connections import (
    connections_for_company_id,
    connections_for_company_ids,
    grouped_connections_by_company,
    import_linkedin_connections,
    latest_import_summary,
    linkedin_connection_count,
    list_linkedin_connections,
    matched_catalog_companies,
    parse_linkedin_connections_csv,
)
from ml_job_swarm.profile import (
    REQUIRED_PREFERENCE_IDS,
    create_target_profile,
    update_preferences,
)
from ml_job_swarm.resume_extract import (
    ResumeExtractionError,
    extract_text_from_bytes,
    parse_resume_text,
    record_parse_run,
)

SUPPORTED_RESUME_TYPES = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
}


class JobDecisionRequest(BaseModel):
    target_profile_id: int
    decision: str
    notes: str = ""


class FindMatchesRequest(BaseModel):
    target_profile_id: int
    llm_consent: bool = False


class ReviewJobsRequest(BaseModel):
    target_profile_id: int
    llm_consent: bool = False


class PreferencesRequest(BaseModel):
    resume_asset_id: int | None = None
    role: str
    level: str
    location: str
    work_mode: str
    company_stage: str


class ReferralContactRequest(BaseModel):
    target_profile_id: int
    name: str
    email: str = ""
    title: str = ""
    relationship: str = ""
    notes: str = ""


class ApplicationPacketStatusRequest(BaseModel):
    target_profile_id: int
    status: str


class VisionFallbackRequest(BaseModel):
    resume_asset_id: int
    consent: bool = True


class ResumeRewriteRequest(BaseModel):
    section_id: int
    target_profile_id: int | None = None
    job_id: int | None = None
    llm_consent: bool = False


class SuggestionActionRequest(BaseModel):
    target_profile_id: int | None = None


def _serialize(value: Any) -> Any:
    if is_dataclass(value):
        return {key: _serialize(item) for key, item in asdict(value).items()}
    if isinstance(value, list):
        return [_serialize(item) for item in value]
    if isinstance(value, dict):
        return {key: _serialize(item) for key, item in value.items()}
    return value


def _company_payload(
    company: CompanyResult,
    connections_by_company_id: dict[int, list[dict[str, object]]],
) -> dict[str, object]:
    payload = _serialize(company)
    connections = connections_by_company_id.get(company.company_id, [])
    payload["linkedin_connections"] = connections
    payload["connection_count"] = len(connections)
    return payload


def _preferences_payload(payload: PreferencesRequest) -> dict[str, dict[str, str]]:
    return {
        "role": {"answer": payload.role.strip()},
        "level": {"answer": payload.level.strip()},
        "location": {"answer": payload.location.strip()},
        "work_mode": {"answer": payload.work_mode.strip()},
        "company_stage": {"answer": payload.company_stage.strip()},
    }


def _keywords_payload(payload: PreferencesRequest) -> dict[str, list[str]]:
    return {
        "desired_titles": [payload.role.strip()],
        "levels": [payload.level.strip()],
        "locations": [payload.location.strip()],
        "remote_modes": [payload.work_mode.strip()],
        "company_stages": [payload.company_stage.strip()],
    }


def _require_supported_resume(resume: UploadFile) -> None:
    suffix = Path(resume.filename or "").suffix.casefold()
    allowed_suffixes = set(SUPPORTED_RESUME_TYPES.values())
    if suffix in allowed_suffixes:
        return
    content_type = (resume.content_type or "").split(";", 1)[0].strip().lower()
    if content_type in SUPPORTED_RESUME_TYPES:
        return
    raise HTTPException(status_code=400, detail="Resume must be a PDF or DOCX file")


def _rules_preview_company_groups(
    conn: sqlite3.Connection,
    previews: list[dict[str, object]],
) -> list[dict[str, object]]:
    grouped: dict[str, list[dict[str, object]]] = {}
    for preview in previews:
        company_name = str(preview.get("company_name") or "")
        grouped.setdefault(company_name, []).append(preview)

    company_ids: dict[str, int] = {}
    for company_name in grouped:
        row = conn.execute(
            "SELECT id FROM companies WHERE name = ? LIMIT 1",
            (company_name,),
        ).fetchone()
        if row is not None:
            company_ids[company_name] = int(row["id"])

    connections_by_company_id = connections_for_company_ids(
        conn,
        list(company_ids.values()),
    )
    results: list[dict[str, object]] = []
    for company_name, jobs in sorted(grouped.items()):
        company_id = company_ids.get(company_name)
        connections = (
            connections_by_company_id.get(company_id, [])
            if company_id is not None
            else []
        )
        results.append(
            {
                "company_name": company_name,
                "company_id": company_id,
                "jobs": jobs,
                "connection_count": len(connections),
                "linkedin_connections": connections,
            }
        )
    return sorted(
        results,
        key=lambda row: (
            -int(row["connection_count"]),
            str(row["company_name"]).casefold(),
        ),
    )


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


def create_api_v1_router(
    *,
    conn: sqlite3.Connection,
    get_adapter_registry: Callable[[], object],
    get_fit_gate_client: Callable[[], object | None],
    filter_companies_by_decision,
    filter_companies_by_connections,
    sort_companies_by_connections,
    dashboard_decision_filter,
    dashboard_connection_filter,
    profile_summary,
    latest_succeeded_run_finished_at,
    job_detail,
    unreviewed_job_rows,
    resume_sections_for_profile: Callable[[sqlite3.Connection, int], list[dict[str, object]]],
    resume_suggestions_for_profile: Callable[[sqlite3.Connection, int], list[dict[str, object]]],
    application_packet_for_job: Callable[..., dict[str, object] | None],
    referral_contacts_for_job: Callable[..., list[dict[str, object]]],
    prepare_application_packet: Callable[..., int],
    add_referral_contact: Callable[..., int],
    company_id_for_job: Callable[[sqlite3.Connection, int], int | None],
    referral_contacts_by_job_id: Callable[
        [sqlite3.Connection, list[int]], dict[int, list[dict[str, object]]]
    ],
    source_health_rows: Callable[..., list[dict[str, object]]],
    source_review_rows: Callable[..., list[dict[str, object]]],
    source_support_summary: Callable[[list[dict[str, object]]], dict[str, int]],
    resume_asset_dir: Path,
    db_path: str,
    get_vision_fallback_provider: Callable[[], object | None],
    get_resume_rewrite_client: Callable[[], object | None],
    resume_section: Callable[[sqlite3.Connection, int], dict[str, object] | None],
    update_resume_suggestion_status: Callable[..., bool],
    review_company_source: Callable[..., dict[str, object]],
    refresh_source: Callable[..., object],
) -> APIRouter:
    router = APIRouter(prefix="/api/v1", tags=["api-v1"])

    @router.get("/llm/usage")
    def llm_usage() -> dict[str, object]:
        return llm_usage_summary(conn)

    @router.get("/health")
    def health() -> dict[str, object]:
        profile_count = conn.execute("SELECT COUNT(*) AS count FROM target_profiles").fetchone()
        job_count = conn.execute("SELECT COUNT(*) AS count FROM jobs").fetchone()
        return {
            "status": "ok",
            "connection_count": linkedin_connection_count(conn),
            "fit_review_available": get_fit_gate_client() is not None,
            "profile_count": int(profile_count["count"]) if profile_count else 0,
            "job_count": int(job_count["count"]) if job_count else 0,
            "db_path": db_path,
        }

    @router.get("/onboarding")
    def onboarding_state(resume_asset_id: int | None = None) -> dict[str, object]:
        profile_count = conn.execute("SELECT COUNT(*) AS count FROM target_profiles").fetchone()
        pending_vision_fallback = False
        if resume_asset_id is not None:
            pending = conn.execute(
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
            pending_vision_fallback = pending is not None
        return {
            "has_profiles": bool(profile_count and int(profile_count["count"]) > 0),
            "preference_fields": list(REQUIRED_PREFERENCE_IDS),
            "resume_asset_id": resume_asset_id,
            "pending_vision_fallback": pending_vision_fallback,
            "fit_review_available": get_fit_gate_client() is not None,
        }

    @router.post("/onboarding/resume")
    async def upload_onboarding_resume(resume: UploadFile = File(...)) -> dict[str, object]:
        _require_supported_resume(resume)
        content = await resume.read()
        if not content:
            raise HTTPException(status_code=400, detail="Resume file is empty")

        digest = hashlib.sha256(content).hexdigest()
        storage_path = persist_resume_asset(
            content,
            original_filename=resume.filename or "resume",
            digest=digest,
            asset_dir=resume_asset_dir,
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

        return {
            "status": "ok",
            "resume_asset_id": resume_asset_id,
            "needs_vision_fallback": parse_result.needs_vision_fallback,
        }

    @router.post("/onboarding/vision-fallback")
    def consent_vision_fallback(payload: VisionFallbackRequest) -> dict[str, object]:
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
            (payload.resume_asset_id,),
        ).fetchone()
        if pending_run is None:
            raise HTTPException(status_code=400, detail="No pending vision fallback")
        if not payload.consent:
            conn.execute(
                "UPDATE resume_parse_runs SET vision_fallback_status = 'declined' WHERE id = ?",
                (pending_run["id"],),
            )
            conn.commit()
            return {"status": "declined", "resume_asset_id": payload.resume_asset_id}

        vision_fallback_provider = get_vision_fallback_provider()
        if vision_fallback_provider is None:
            raise HTTPException(
                status_code=503,
                detail="Vision fallback provider is not configured",
            )

        asset = conn.execute(
            """
            SELECT original_filename, content_type, storage_path
            FROM resume_assets
            WHERE id = ?
            """,
            (payload.resume_asset_id,),
        ).fetchone()
        if asset is None:
            raise HTTPException(status_code=404, detail="Resume asset not found")
        try:
            asset_content = load_resume_asset_bytes(
                asset["storage_path"],
                resume_asset_dir,
            )
            private_content_parts = pdf_page_image_content_parts(asset_content)
        except ResumeAssetStorageError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

        consented_at = datetime.now(UTC)
        llm_request = LLMRequest(
            feature="resume_vision_fallback",
            schema_version=getattr(
                vision_fallback_provider, "schema_version", "vision_fallback.v1"
            ),
            model=getattr(vision_fallback_provider, "model", "openrouter/vision"),
            input_reference=f"resume_asset:{payload.resume_asset_id}",
            private_prompt=(
                "User consented to vision fallback for "
                f"resume_asset:{payload.resume_asset_id} at {consented_at.isoformat()}. "
                "Extract resume text as strict JSON."
            ),
            private_content_parts=private_content_parts,
            provider=getattr(vision_fallback_provider, "provider", "openrouter"),
        )
        try:
            response = request_structured_response(
                conn,
                vision_fallback_provider,
                llm_request,
                VisionFallbackResponse,
            )
        except ValidationError as exc:
            raise HTTPException(
                status_code=502,
                detail="Vision fallback response was invalid",
            ) from exc

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
            resume_asset_id=payload.resume_asset_id,
            result=parse_result,
            consented_at=None,
        )
        return {
            "status": "ok",
            "resume_asset_id": payload.resume_asset_id,
            "needs_vision_fallback": parse_result.needs_vision_fallback,
        }

    @router.post("/onboarding/preferences")
    def create_onboarding_preferences(payload: PreferencesRequest) -> dict[str, object]:
        if payload.resume_asset_id is None:
            raise HTTPException(
                status_code=400,
                detail="Upload a resume before saving preferences",
            )
        missing = [
            field
            for field in REQUIRED_PREFERENCE_IDS
            if not getattr(payload, field).strip()
        ]
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"Missing required preference fields: {', '.join(missing)}",
            )
        try:
            target_profile_id = create_target_profile(
                conn,
                resume_asset_id=payload.resume_asset_id,
                keywords=_keywords_payload(payload),
                preferences=_preferences_payload(payload),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {
            "status": "ok",
            "target_profile_id": target_profile_id,
        }

    @router.get("/profiles")
    def list_profiles() -> dict[str, object]:
        rows = conn.execute(
            """
            SELECT id, name, version, active
            FROM target_profiles
            ORDER BY id DESC
            """
        ).fetchall()
        return {"profiles": [dict(row) for row in rows]}

    @router.get("/profiles/{target_profile_id}")
    def get_profile(target_profile_id: int) -> dict[str, object]:
        try:
            return profile_summary(conn, target_profile_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.put("/profiles/{target_profile_id}/preferences")
    def update_profile_preferences(
        target_profile_id: int,
        payload: PreferencesRequest,
    ) -> dict[str, object]:
        missing = [
            field
            for field in REQUIRED_PREFERENCE_IDS
            if not getattr(payload, field).strip()
        ]
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"Missing required preference fields: {', '.join(missing)}",
            )
        try:
            version = update_preferences(
                conn,
                target_profile_id,
                _preferences_payload(payload),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"status": "ok", "version": version}

    @router.get("/profiles/{target_profile_id}/workspace")
    def profile_workspace(target_profile_id: int) -> dict[str, object]:
        try:
            summary = profile_summary(conn, target_profile_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return {
            "profile_summary": summary,
            "resume_sections": resume_sections_for_profile(conn, target_profile_id),
            "resume_suggestions": resume_suggestions_for_profile(conn, target_profile_id),
        }

    @router.get("/dashboard")
    def dashboard(
        target_profile_id: int,
        decision_filter: str = "all",
        connection_filter: str = "all",
    ) -> dict[str, object]:
        active_decision_filter = dashboard_decision_filter(decision_filter)
        active_connection_filter = dashboard_connection_filter(connection_filter)
        try:
            companies = visible_company_results(conn, target_profile_id)
            companies = filter_companies_by_decision(
                companies, active_decision_filter
            )
            connections_by_company_id = connections_for_company_ids(
                conn,
                [company.company_id for company in companies],
            )
            companies = filter_companies_by_connections(
                companies,
                connections_by_company_id,
                active_connection_filter,
            )
            companies = sort_companies_by_connections(
                companies,
                connections_by_company_id,
            )
            summary = profile_summary(conn, target_profile_id)
            sections = resume_sections_for_profile(conn, target_profile_id)
            suggestions = resume_suggestions_for_profile(conn, target_profile_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        return {
            "target_profile_id": target_profile_id,
            "decision_filter": active_decision_filter,
            "connection_filter": active_connection_filter,
            "connection_count": linkedin_connection_count(conn),
            "catalog_refreshed_at": latest_succeeded_run_finished_at(conn),
            "fit_review_available": get_fit_gate_client() is not None,
            "profile_summary": summary,
            "resume_sections": sections,
            "resume_suggestions": suggestions,
            "companies": [
                _company_payload(company, connections_by_company_id)
                for company in companies
            ],
            "rules_preview_jobs": _serialize(preview_jobs := rules_preview_jobs(conn, target_profile_id)),
            "rules_preview_companies": _rules_preview_company_groups(
                conn,
                _serialize(preview_jobs),
            ),
            "referral_network": [
                {
                    "company_id": match.company_id,
                    "company_name": match.company_name,
                    "connections": list(match.connections),
                }
                for match in matched_catalog_companies(conn)
            ],
            "unreviewed_jobs": unreviewed_job_rows(conn, target_profile_id),
        }

    @router.get("/saved-jobs/export.csv")
    def export_saved_jobs_csv(
        target_profile_id: int,
        q: str = "",
        sort: str = "recent",
    ):
        from fastapi.responses import Response

        try:
            rows = saved_job_export_rows(conn, target_profile_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        sort_key = sort if sort in {"recent", "score", "company", "title"} else "recent"
        query = q.strip()
        filtered_rows = _sort_saved_jobs(_filter_saved_jobs(rows, query), sort_key)

        import csv
        import io

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
        for row in filtered_rows:
            writer.writerow(row)
        return Response(output.getvalue(), media_type="text/csv")

    @router.get("/saved-jobs")
    def saved_jobs(
        target_profile_id: int,
        q: str = "",
        sort: str = "recent",
    ) -> dict[str, object]:
        try:
            rows = saved_job_export_rows(conn, target_profile_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        sort_key = sort if sort in {"recent", "score", "company", "title"} else "recent"
        query = q.strip()
        filtered_rows = _sort_saved_jobs(_filter_saved_jobs(rows, query), sort_key)
        contacts_by_job_id = referral_contacts_by_job_id(
            conn,
            [int(row["job_id"]) for row in filtered_rows],
        )
        for row in filtered_rows:
            row["referral_contacts"] = contacts_by_job_id.get(int(row["job_id"]), [])
        return {
            "target_profile_id": target_profile_id,
            "query": query,
            "sort": sort_key,
            "saved_jobs": filtered_rows,
            "has_saved_jobs": bool(rows),
        }

    @router.get("/jobs/{job_id}")
    def get_job(job_id: int, target_profile_id: int) -> dict[str, object]:
        detail = job_detail(conn, job_id, target_profile_id)
        if detail is None:
            raise HTTPException(status_code=404, detail="Job not found")
        company_id_row = conn.execute(
            "SELECT company_id FROM jobs WHERE id = ?",
            (job_id,),
        ).fetchone()
        company_id = int(company_id_row["company_id"]) if company_id_row else None
        linkedin = (
            connections_for_company_id(conn, company_id)
            if company_id is not None
            else []
        )
        packet = application_packet_for_job(
            conn,
            job_id=job_id,
            target_profile_id=target_profile_id,
        )
        return {
            "job": detail,
            "linkedin_connections": linkedin,
            "referral_contacts": referral_contacts_for_job(conn, job_id=job_id),
            "application_packet": packet,
        }

    @router.post("/jobs/{job_id}/decision")
    def set_job_decision(job_id: int, payload: JobDecisionRequest) -> dict[str, str]:
        from ml_job_swarm.decisions import clear_job_decision, record_job_decision

        if payload.decision not in {"saved", "hidden", "clear"}:
            raise HTTPException(status_code=400, detail="Invalid decision")
        if payload.decision == "clear":
            clear_job_decision(
                conn,
                job_id=job_id,
                target_profile_id=payload.target_profile_id,
            )
        else:
            record_job_decision(
                conn,
                job_id=job_id,
                target_profile_id=payload.target_profile_id,
                decision=payload.decision,
                notes=payload.notes,
            )
        return {"status": "ok"}

    @router.post("/jobs/{job_id}/referral-contacts")
    def create_referral_contact(
        job_id: int,
        payload: ReferralContactRequest,
    ) -> dict[str, object]:
        if not payload.name.strip():
            raise HTTPException(status_code=400, detail="name is required")
        company_id = company_id_for_job(conn, job_id)
        if company_id is None:
            raise HTTPException(status_code=404, detail="Job not found")
        contact_id = add_referral_contact(
            conn,
            company_id=company_id,
            name=payload.name.strip(),
            email=payload.email.strip(),
            title=payload.title.strip(),
            relationship=payload.relationship.strip(),
            notes=payload.notes.strip(),
        )
        return {"status": "ok", "contact_id": contact_id}

    @router.post("/jobs/{job_id}/application-packet")
    def create_application_packet(
        job_id: int,
        target_profile_id: int,
    ) -> dict[str, object]:
        try:
            packet_id = prepare_application_packet(
                conn,
                job_id=job_id,
                target_profile_id=target_profile_id,
            )
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        packet = application_packet_for_job(
            conn,
            job_id=job_id,
            target_profile_id=target_profile_id,
        )
        return {"status": "ok", "packet_id": packet_id, "application_packet": packet}

    @router.post("/application-packets/{packet_id}/status")
    def update_packet_status(
        packet_id: int,
        payload: ApplicationPacketStatusRequest,
    ) -> dict[str, str]:
        if payload.status not in {"prepared", "submitted"}:
            raise HTTPException(
                status_code=400,
                detail="status must be prepared or submitted",
            )
        row = conn.execute(
            """
            SELECT job_id
            FROM application_packets
            WHERE id = ?
              AND target_profile_id = ?
            """,
            (packet_id, payload.target_profile_id),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Application packet not found")
        conn.execute(
            """
            UPDATE application_packets
            SET status = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (payload.status, packet_id),
        )
        conn.commit()
        return {"status": "ok"}

    @router.post("/dashboard/refresh-sources")
    def refresh_sources(target_profile_id: int) -> dict[str, object]:
        del target_profile_id
        summary = refresh_due_sources(
            conn,
            adapter_registry=get_adapter_registry(),
        )
        return {"status": "ok", "summary": _serialize(summary)}

    @router.post("/dashboard/find-matches")
    def find_matches(payload: FindMatchesRequest) -> dict[str, object]:
        refresh_summary = refresh_due_sources(
            conn,
            adapter_registry=get_adapter_registry(),
        )
        fit_gate_client = get_fit_gate_client()
        if fit_gate_client is None:
            return {
                "status": "refresh_only",
                "refresh_summary": _serialize(refresh_summary),
                "review": None,
            }
        if not payload.llm_consent:
            raise HTTPException(
                status_code=400,
                detail="LLM consent is required for fit review",
            )
        review = review_jobs_for_profile_resilient(
            conn,
            payload.target_profile_id,
            fit_gate_client,
        )
        return {
            "status": "ok",
            "refresh_summary": _serialize(refresh_summary),
            "review": _serialize(review),
        }

    @router.post("/dashboard/review-jobs")
    def review_jobs(payload: ReviewJobsRequest) -> dict[str, object]:
        fit_gate_client = get_fit_gate_client()
        if fit_gate_client is None:
            raise HTTPException(status_code=503, detail="Fit review client unavailable")
        if not payload.llm_consent:
            raise HTTPException(
                status_code=400,
                detail="LLM consent is required for fit review",
            )
        try:
            review_jobs_for_profile(
                conn,
                payload.target_profile_id,
                fit_gate_client,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"status": "ok"}

    @router.get("/connections")
    def connections(search: str = "") -> dict[str, object]:
        return {
            "connection_count": linkedin_connection_count(conn),
            "latest_import": latest_import_summary(conn),
            "grouped_companies": grouped_connections_by_company(conn, search=search),
            "matched_catalog": [
                {
                    "company_id": match.company_id,
                    "company_name": match.company_name,
                    "connections": list(match.connections),
                }
                for match in matched_catalog_companies(conn)
            ],
            "connections": list_linkedin_connections(conn, search=search),
        }

    @router.post("/connections/import")
    async def import_connections(connections_file: UploadFile = File(...)) -> dict[str, object]:
        content = await connections_file.read()
        if not content:
            raise HTTPException(status_code=400, detail="Uploaded file was empty")
        try:
            parsed = parse_linkedin_connections_csv(content.decode("utf-8-sig"))
            result = import_linkedin_connections(
                conn,
                connections=parsed,
                filename=connections_file.filename or "Connections.csv",
            )
        except (UnicodeDecodeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {
            "status": "ok",
            "imported": result.imported,
            "updated": result.updated,
            "skipped": result.skipped,
            "import_id": result.import_id,
        }

    @router.post("/profiles/{target_profile_id}/resume/rewrite")
    def rewrite_resume_section(
        target_profile_id: int,
        payload: ResumeRewriteRequest,
    ) -> dict[str, object]:
        if payload.target_profile_id is not None and payload.target_profile_id != target_profile_id:
            raise HTTPException(status_code=400, detail="target_profile_id mismatch")
        if not payload.llm_consent:
            raise HTTPException(status_code=400, detail="LLM consent is required")
        resume_rewrite_client = get_resume_rewrite_client()
        if resume_rewrite_client is None:
            raise HTTPException(status_code=503, detail="Resume rewrite client unavailable")

        section = resume_section(conn, payload.section_id)
        if section is None:
            raise HTTPException(status_code=404, detail="Resume section not found")

        rewrite_payload = {
            "section_id": payload.section_id,
            "target_profile_id": target_profile_id,
            "job_id": payload.job_id,
            "heading": section["heading"],
            "section_type": section["section_type"],
            "text": section["text"],
        }
        llm_request = LLMRequest(
            feature="resume_rewrite",
            schema_version=getattr(
                resume_rewrite_client, "schema_version", "resume_rewrite.v1"
            ),
            model=getattr(resume_rewrite_client, "model", "unknown"),
            provider=getattr(resume_rewrite_client, "provider", "openrouter"),
            input_reference=(
                f"resume_asset:{section['resume_asset_id']}|section:{payload.section_id}"
            ),
            private_prompt=str(section["text"]),
        )
        raw_response: dict[str, object] = {}
        try:
            raw_response = resume_rewrite_client.rewrite_section(rewrite_payload)
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
            raise HTTPException(status_code=502, detail="Resume rewrite failed") from exc

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
                payload.job_id,
                target_profile_id,
                payload.section_id,
                llm_request_id,
                response.replacement_text,
            ),
        )
        conn.commit()
        return {
            "status": "ok",
            "suggestion_id": int(cursor.lastrowid),
            "suggestion_text": response.replacement_text,
        }

    @router.post("/resume/suggestions/{suggestion_id}/accept")
    def accept_resume_suggestion(
        suggestion_id: int,
        payload: SuggestionActionRequest,
    ) -> dict[str, str]:
        updated = update_resume_suggestion_status(
            conn,
            suggestion_id,
            "accepted",
            payload.target_profile_id,
        )
        if not updated:
            raise HTTPException(status_code=404, detail="Suggestion not found")
        return {"status": "ok"}

    @router.post("/resume/suggestions/{suggestion_id}/reject")
    def reject_resume_suggestion(
        suggestion_id: int,
        payload: SuggestionActionRequest,
    ) -> dict[str, str]:
        updated = update_resume_suggestion_status(
            conn,
            suggestion_id,
            "rejected",
            payload.target_profile_id,
        )
        if not updated:
            raise HTTPException(status_code=404, detail="Suggestion not found")
        return {"status": "ok"}

    @router.get("/admin/sources")
    def admin_sources() -> dict[str, object]:
        adapter_registry = get_adapter_registry()
        source_types = adapter_registry.source_types()
        sources = source_health_rows(conn, source_types)
        reviews = source_review_rows(conn, source_types)
        return {
            "sources": sources,
            "source_reviews": reviews,
            "support_summary": source_support_summary(sources),
        }

    @router.post("/admin/sources/refresh")
    def refresh_admin_sources() -> dict[str, object]:
        summary = refresh_due_sources(
            conn,
            adapter_registry=get_adapter_registry(),
        )
        return {"status": "ok", "summary": _serialize(summary)}

    @router.post("/admin/sources/{source_id}/refresh")
    def refresh_admin_source(source_id: int) -> dict[str, object]:
        source = conn.execute(
            """
            SELECT source_type, disabled_at
            FROM job_sources
            WHERE id = ?
            """,
            (source_id,),
        ).fetchone()
        if source is None:
            raise HTTPException(status_code=404, detail="Source not found")
        if source["disabled_at"] is not None:
            raise HTTPException(status_code=400, detail="Source disabled")
        adapter_registry = get_adapter_registry()
        source_types = adapter_registry.source_types()
        if source["source_type"] not in source_types:
            raise HTTPException(status_code=400, detail="Unsupported source type")
        refresh_result = refresh_source(
            conn,
            source_id,
            adapter_registry.adapter_for(source["source_type"]),
        )
        return {"status": "ok", "summary": _serialize(refresh_result)}

    @router.post("/admin/source-review/{queue_id}/approve")
    def approve_source_review(queue_id: int) -> dict[str, object]:
        try:
            result = review_company_source(conn, queue_id, "approve")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"status": "ok", "result": result}

    @router.post("/admin/source-review/{queue_id}/reject")
    def reject_source_review(queue_id: int) -> dict[str, object]:
        try:
            result = review_company_source(conn, queue_id, "reject")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"status": "ok", "result": result}

    return router