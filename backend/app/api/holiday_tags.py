from __future__ import annotations

from fastapi import APIRouter, Depends
from psycopg import Connection

from app.api.deps import get_current_user, require_admin
from app.db import get_connection
from app.services.holiday_tags import refresh_holiday_tags

router = APIRouter(prefix="/holiday-tags", tags=["holiday-tags"])


@router.post("/refresh")
def refresh_tags(
    marketplace: str = "UK",
    current_user: dict = Depends(require_admin),
    conn: Connection = Depends(get_connection),
) -> dict[str, object]:
    """Rebuild all keyword holiday tags for the given marketplace."""
    count = refresh_holiday_tags(conn, marketplace=marketplace)
    return {"ok": True, "count": count}


@router.get("/stats")
def tag_stats(
    marketplace: str = "UK",
    current_user: dict = Depends(get_current_user),
    conn: Connection = Depends(get_connection),
) -> dict[str, object]:
    """Return summary counts of holiday tags."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE confidence = 'confirmed') AS confirmed,
                COUNT(*) FILTER (WHERE confidence = 'suspected') AS suspected
            FROM keyword_holiday_tags
            WHERE marketplace = %s
            """,
            [marketplace],
        )
        row = cur.fetchone()
    return {
        "total": row["total"],
        "confirmed": row["confirmed"],
        "suspected": row["suspected"],
    }
