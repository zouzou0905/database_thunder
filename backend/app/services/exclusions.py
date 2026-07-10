from __future__ import annotations

from typing import Any

import psycopg


def list_exclusions(conn: psycopg.Connection, active_only: bool = False) -> list[dict[str, Any]]:
    where = "WHERE is_active = TRUE" if active_only else ""
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT
                id,
                term,
                match_type,
                exclusion_type,
                reason,
                is_active,
                created_at,
                updated_at
            FROM keyword_selection_exclusions
            {where}
            ORDER BY is_active DESC, updated_at DESC, term
            """
        )
        return cur.fetchall()


def upsert_exclusion(
    conn: psycopg.Connection,
    *,
    term: str,
    match_type: str,
    exclusion_type: str,
    reason: str | None,
    is_active: bool,
) -> dict[str, Any]:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO keyword_selection_exclusions (
                term,
                match_type,
                exclusion_type,
                reason,
                is_active
            )
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (term, match_type, exclusion_type)
            DO UPDATE SET
                reason = EXCLUDED.reason,
                is_active = EXCLUDED.is_active,
                updated_at = NOW()
            RETURNING *
            """,
            [term.strip().lower(), match_type, exclusion_type, reason, is_active],
        )
        row = cur.fetchone()
    conn.commit()
    return row


def update_exclusion(
    conn: psycopg.Connection,
    exclusion_id: int,
    *,
    reason: str | None = None,
    is_active: bool | None = None,
) -> dict[str, Any] | None:
    assignments: list[str] = []
    params: list[Any] = []
    if reason is not None:
        assignments.append("reason = %s")
        params.append(reason)
    if is_active is not None:
        assignments.append("is_active = %s")
        params.append(is_active)
    assignments.append("updated_at = NOW()")
    params.append(exclusion_id)

    with conn.cursor() as cur:
        cur.execute(
            f"""
            UPDATE keyword_selection_exclusions
            SET {", ".join(assignments)}
            WHERE id = %s
            RETURNING *
            """,
            params,
        )
        row = cur.fetchone()
    conn.commit()
    return row


def delete_exclusion(conn: psycopg.Connection, exclusion_id: int) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            """
            DELETE FROM keyword_selection_exclusions
            WHERE id = %s
            """,
            [exclusion_id],
        )
        deleted = cur.rowcount > 0
    conn.commit()
    return deleted
