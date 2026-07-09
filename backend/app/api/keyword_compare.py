from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from psycopg import Connection

from app.api.deps import get_current_user
from app.db import get_connection
from app.services.keyword_compare import KeywordCompareFilters, list_keyword_comparisons
from app.utils.json import to_jsonable


router = APIRouter(prefix="/keyword-compare", tags=["keyword-compare"])


@router.get("/keywords")
def keyword_comparisons(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=500),
    start_month: str | None = Query(default=None),
    end_month: str | None = Query(default=None),
    marketplace: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    category: str | None = Query(default=None),
    trend_type: str | None = Query(default=None),
    holiday_code: str | None = Query(default=None),
    search_volume_min: float | None = Query(default=None),
    search_volume_max: float | None = Query(default=None),
    growth_rate_min: float | None = Query(default=None),
    growth_rate_max: float | None = Query(default=None),
    month_count_min: int | None = Query(default=None, ge=1),
    month_count_max: int | None = Query(default=None, ge=1),
    ppc_min: float | None = Query(default=None),
    ppc_max: float | None = Query(default=None),
    spr_min: int | None = Query(default=None),
    spr_max: int | None = Query(default=None),
    sort_by: str = Query(default="growth_rate"),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$"),
    current_user: dict = Depends(get_current_user),
    conn: Connection = Depends(get_connection),
) -> dict[str, object]:
    filters = KeywordCompareFilters(
        page=page,
        page_size=page_size,
        start_month=start_month,
        end_month=end_month,
        marketplace=marketplace,
        keyword=keyword,
        category=category,
        trend_type=trend_type,
        holiday_code=holiday_code,
        search_volume_min=search_volume_min,
        search_volume_max=search_volume_max,
        growth_rate_min=growth_rate_min,
        growth_rate_max=growth_rate_max,
        month_count_min=month_count_min,
        month_count_max=month_count_max,
        ppc_min=ppc_min,
        ppc_max=ppc_max,
        spr_min=spr_min,
        spr_max=spr_max,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return to_jsonable(list_keyword_comparisons(conn, filters, user_id=current_user["id"]))
