from __future__ import annotations

from typing import get_args

from ml_job_swarm.db.connection import StoreConnection
from ml_job_swarm.models import JobDecision
from ml_job_swarm.profile import current_profile_version


VALID_JOB_DECISIONS = set(get_args(JobDecision))


def record_job_decision(
    conn: StoreConnection,
    *,
    job_id: int,
    target_profile_id: int,
    decision: str,
    notes: str = "",
) -> int:
    if decision not in VALID_JOB_DECISIONS:
        raise ValueError("Invalid job decision")
    _require_job_and_profile(conn, job_id, target_profile_id)

    conn.execute(
        """
        INSERT INTO job_decisions (
          job_id,
          target_profile_id,
          decision,
          notes
        )
        VALUES (?, ?, ?, ?)
        ON CONFLICT(job_id, target_profile_id)
        DO UPDATE SET
          decision = excluded.decision,
          notes = excluded.notes,
          updated_at = CURRENT_TIMESTAMP
        """,
        (job_id, target_profile_id, decision, notes),
    )
    conn.commit()
    return int(
        conn.execute(
            """
            SELECT id
            FROM job_decisions
            WHERE job_id = ? AND target_profile_id = ?
            """,
            (job_id, target_profile_id),
        ).fetchone()["id"]
    )


def clear_job_decision(
    conn: StoreConnection, *, job_id: int, target_profile_id: int
) -> None:
    _require_job_and_profile(conn, job_id, target_profile_id)
    conn.execute(
        """
        DELETE FROM job_decisions
        WHERE job_id = ? AND target_profile_id = ?
        """,
        (job_id, target_profile_id),
    )
    conn.commit()


def saved_job_export_rows(
    conn: StoreConnection, target_profile_id: int
) -> list[dict[str, object]]:
    profile_version = current_profile_version(conn, target_profile_id)
    rows = conn.execute(
        """
        SELECT
          jobs.id AS job_id,
          companies.name AS company,
          jobs.title,
          fit_reviews.fit_score,
          COALESCE(fit_reviews.label, 'Not reviewed') AS label,
          COALESCE(fit_reviews.recommendation, '') AS recommendation,
          COALESCE(jobs.apply_url, '') AS apply_url,
          jobs.source_url,
          application_packets.id AS application_packet_id,
          COALESCE(application_packets.status, 'not_prepared') AS packet_status,
          COALESCE(application_packets.manual_submit_url, '') AS manual_submit_url,
          application_packets.updated_at AS packet_updated_at,
          job_decisions.decision,
          job_decisions.notes,
          job_decisions.updated_at AS decided_at
        FROM job_decisions
        JOIN jobs ON jobs.id = job_decisions.job_id
        JOIN companies ON companies.id = jobs.company_id
        LEFT JOIN fit_reviews
          ON fit_reviews.id = (
            SELECT MAX(id)
            FROM fit_reviews
            WHERE job_id = jobs.id
              AND target_profile_id = job_decisions.target_profile_id
              AND profile_version = ?
          )
        LEFT JOIN application_packets
          ON application_packets.job_id = jobs.id
         AND application_packets.target_profile_id = job_decisions.target_profile_id
        WHERE job_decisions.target_profile_id = ?
          AND job_decisions.decision = 'saved'
        ORDER BY job_decisions.updated_at DESC, companies.name, jobs.title
        """,
        (profile_version, target_profile_id),
    ).fetchall()
    return [dict(row) for row in rows]


def _require_job_and_profile(
    conn: StoreConnection, job_id: int, target_profile_id: int
) -> None:
    job = conn.execute("SELECT id FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if job is None:
        raise ValueError("Job not found")
    profile = conn.execute(
        "SELECT id FROM target_profiles WHERE id = ?",
        (target_profile_id,),
    ).fetchone()
    if profile is None:
        raise ValueError("Target profile not found")
