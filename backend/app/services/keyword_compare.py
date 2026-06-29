from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

import psycopg


SORT_COLUMNS = {
    "keyword": "keyword",
    "growth_rate": "search_volume_growth_rate",
    "volume_change": "search_volume_change",
    "end_search_volume": "end_search_volume",
    "start_search_volume": "start_search_volume",
    "rank_change": "rank_change",
    "month_count": "month_count",
}

TREND_LABELS_CN = {
    "rising": "上升型",
    "falling": "下降型",
    "stable": "常年稳定型",
    "seasonal": "季节型",
    "volatile": "波动型",
}


@dataclass(frozen=True)
class KeywordCompareFilters:
    page: int = 1
    page_size: int = 100
    start_month: str | None = None
    end_month: str | None = None
    marketplace: str | None = None
    keyword: str | None = None
    category: str | None = None
    trend_type: str | None = None
    search_volume_min: float | None = None
    search_volume_max: float | None = None
    growth_rate_min: float | None = None
    growth_rate_max: float | None = None
    month_count_min: int | None = None
    ppc_max: float | None = None
    spr_max: int | None = None
    sort_by: str = "growth_rate"
    sort_order: str = "desc"


def _build_where(filters: KeywordCompareFilters) -> tuple[str, dict[str, Any]]:
    """Build WHERE clause from filters, matching the original interface.

    The snapshot table stores data computed for the full date range.  When
    start_month / end_month are provided we restrict on first_month /
    last_month boundaries — this is an approximation of the exact trend type
    for arbitrary sub-ranges, but matches the common operational use case
    (default = full range).
    """
    where: list[str] = ["1 = 1"]
    params: dict[str, Any] = {}

    if filters.marketplace:
        where.append("s.marketplace = %(marketplace)s")
        params["marketplace"] = filters.marketplace

    if filters.start_month:
        start_dt = _month_to_date(filters.start_month)
        if start_dt:
            where.append("s.last_month >= %(start_month)s")
            params["start_month"] = start_dt

    if filters.end_month:
        end_dt = _month_to_date(filters.end_month)
        if end_dt:
            where.append("s.first_month <= %(end_month)s")
            params["end_month"] = end_dt

    if filters.trend_type:
        where.append("s.trend_type = %(trend_type)s")
        params["trend_type"] = filters.trend_type

    if filters.category:
        where.append("s.category = %(category)s")
        params["category"] = filters.category

    if filters.keyword:
        kw_like = f"%{filters.keyword}%"
        where.append("(s.keyword ILIKE %(keyword)s OR s.keyword_translation ILIKE %(keyword)s)")
        params["keyword"] = kw_like

    if filters.search_volume_min is not None:
        where.append("s.end_search_volume >= %(search_volume_min)s")
        params["search_volume_min"] = filters.search_volume_min

    if filters.search_volume_max is not None:
        where.append("s.end_search_volume <= %(search_volume_max)s")
        params["search_volume_max"] = filters.search_volume_max

    if filters.growth_rate_min is not None:
        where.append("s.search_volume_growth_rate >= %(growth_rate_min)s")
        params["growth_rate_min"] = filters.growth_rate_min

    if filters.growth_rate_max is not None:
        where.append("s.search_volume_growth_rate <= %(growth_rate_max)s")
        params["growth_rate_max"] = filters.growth_rate_max

    if filters.month_count_min is not None:
        where.append("s.month_count >= %(month_count_min)s")
        params["month_count_min"] = filters.month_count_min

    if filters.ppc_max is not None:
        where.append("s.ppc_bid_mid <= %(ppc_max)s")
        params["ppc_max"] = filters.ppc_max

    if filters.spr_max is not None:
        where.append("s.spr <= %(spr_max)s")
        params["spr_max"] = filters.spr_max

    return " AND ".join(where), params


def _month_to_date(value: str | None) -> date | None:
    if not value:
        return None
    text = value.strip()
    if len(text) == 7:
        text = f"{text}-01"
    return date.fromisoformat(text)


def _resolve_range(conn: psycopg.Connection, filters: KeywordCompareFilters) -> tuple[date, date]:
    """Return (start_month, end_month) for the months dropdown in the UI."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                MIN(data_month) AS min_month,
                MAX(data_month) AS max_month
            FROM keyword_monthly_metrics
            WHERE (%(marketplace)s::text IS NULL OR marketplace = %(marketplace)s::text)
            """,
            {"marketplace": filters.marketplace},
        )
        row = cur.fetchone()
    if not row or not row["min_month"] or not row["max_month"]:
        raise ValueError("没有可用于横向对比的月份数据")

    start_month = _month_to_date(filters.start_month) or row["min_month"]
    end_month = _month_to_date(filters.end_month) or row["max_month"]
    if start_month > end_month:
        start_month, end_month = end_month, start_month
    return start_month, end_month


def list_keyword_comparisons(
    conn: psycopg.Connection,
    filters: KeywordCompareFilters,
    user_id: int | None = None,
) -> dict[str, Any]:
    start_month, end_month = _resolve_range(conn, filters)
    where_sql, params = _build_where(filters)

    page = max(filters.page, 1)
    page_size = min(max(filters.page_size, 1), 500)
    offset = (page - 1) * page_size
    sort_column = SORT_COLUMNS.get(filters.sort_by, "search_volume_growth_rate")
    sort_order = "ASC" if filters.sort_order.lower() == "asc" else "DESC"

    select_sql = f"""
        SELECT
            s.keyword_id,
            s.keyword,
            s.keyword_translation,
            s.category,
            s.marketplace,
            s.first_month,
            s.last_month,
            s.start_search_volume,
            s.end_search_volume,
            s.search_volume_change,
            s.search_volume_growth_rate,
            s.start_rank AS start_rank,
            s.end_rank AS end_rank,
            s.rank_change,
            s.month_count,
            s.total_months,
            s.ppc_bid_mid,
            s.spr,
            s.prev_month_rank,
            s.four_months_ago_rank,
            s.twelve_months_ago_rank,
            s.trend_type,
            s.trend_type_cn,
            s.monthly,
            state.status AS user_status,
            state.priority AS user_priority,
            COALESCE(state.is_favorite, FALSE) AS user_is_favorite,
            state.notes AS user_notes
        FROM keyword_compare_snapshot s
        LEFT JOIN keyword_selection_states state
          ON state.keyword_id = s.keyword_id
         AND state.analysis_month = s.last_month
         AND state.marketplace = s.marketplace
         AND state.owner_user_id = %(user_id)s::int
        WHERE {where_sql}
        ORDER BY {sort_column} {sort_order} NULLS LAST, s.end_search_volume DESC NULLS LAST, s.keyword ASC
        LIMIT %(limit)s OFFSET %(offset)s
    """

    with conn.cursor() as cur:
        # Months list for the UI dropdown
        cur.execute(
            """
            SELECT data_month
            FROM (
                SELECT DISTINCT data_month
                FROM keyword_monthly_metrics
                WHERE data_month BETWEEN %(start_month)s AND %(end_month)s
                  AND (%(marketplace)s::text IS NULL OR marketplace = %(marketplace)s::text)
            ) m
            ORDER BY data_month
            """,
            {
                "start_month": start_month,
                "end_month": end_month,
                "marketplace": filters.marketplace,
            },
        )
        months = [row["data_month"] for row in cur.fetchall()]

        cur.execute(
            select_sql,
            {**params, "user_id": user_id, "limit": page_size + 1, "offset": offset},
        )
        items = cur.fetchall()

    has_more = len(items) > page_size
    if has_more:
        items = items[:page_size]
    for item in items:
        if not item.get("trend_type_cn"):
            item["trend_type_cn"] = TREND_LABELS_CN.get(item["trend_type"], item["trend_type"])

    total_lower_bound = offset + len(items) + (1 if has_more else 0)

    return {
        "items": items,
        "months": [{"data_month": month} for month in months],
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total_lower_bound,
            "total_pages": page + (1 if has_more else 0),
            "total_is_estimated": True,
            "total_label": "lower_bound",
            "has_more": has_more,
        },
    }
