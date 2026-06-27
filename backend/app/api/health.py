from __future__ import annotations

from fastapi import APIRouter, Depends
from psycopg import Connection

from app.db import get_connection


router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
def health_check(conn: Connection = Depends(get_connection)) -> dict[str, str]:
    with conn.cursor() as cur:
        cur.execute("SELECT 1 AS ok")
        cur.fetchone()
    return {"status": "ok"}
