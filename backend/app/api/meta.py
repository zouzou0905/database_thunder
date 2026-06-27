from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from psycopg import Connection

from app.core.cache import cached
from app.db import get_connection
from app.services.product_selection import list_categories, list_months
from app.utils.json import to_jsonable


router = APIRouter(prefix="/meta", tags=["meta"])


@router.get("/months")
@cached(ttl_seconds=300, namespace="meta", exclude=("conn",))
def months(conn: Connection = Depends(get_connection)) -> dict[str, object]:
    return {"items": to_jsonable(list_months(conn))}


@router.get("/categories")
@cached(ttl_seconds=300, namespace="meta", exclude=("conn",))
def categories(
    analysis_month: str | None = Query(default=None),
    marketplace: str | None = Query(default=None),
    conn: Connection = Depends(get_connection),
) -> dict[str, object]:
    items = list_categories(conn, analysis_month=analysis_month, marketplace=marketplace)
    return {"items": to_jsonable(items)}
