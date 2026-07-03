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

SOURCE_COLUMNS = """
    keyword_id,
    keyword,
    keyword_translation,
    category,
    marketplace,
    first_month,
    last_month,
    start_search_volume,
    end_search_volume,
    search_volume_change,
    search_volume_growth_rate,
    start_rank,
    end_rank,
    rank_change,
    month_count,
    total_months,
    avg_search_volume,
    ppc_bid_mid,
    spr,
    prev_month_rank,
    four_months_ago_rank,
    twelve_months_ago_rank,
    trend_type,
    trend_type_cn,
    monthly,
    prev_month_search_volume,
    yoy_search_volume,
    mom_change,
    mom_rate,
    yoy_change,
    yoy_rate
"""


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
    month_count_max: int | None = None
    ppc_min: float | None = None
    ppc_max: float | None = None
    spr_min: int | None = None
    spr_max: int | None = None
    sort_by: str = "growth_rate"
    sort_order: str = "desc"


def _base_where(filters: KeywordCompareFilters) -> tuple[str, dict[str, Any]]:
    where: list[str] = [
        "m.data_month BETWEEN %(start_month)s AND %(end_month)s",
    ]
    params: dict[str, Any] = {}

    if filters.marketplace:
        where.append("m.marketplace = %(marketplace)s")
        params["marketplace"] = filters.marketplace

    return " AND ".join(where), params


def _result_where(filters: KeywordCompareFilters) -> tuple[str, dict[str, Any]]:
    where: list[str] = ["1 = 1"]
    params: dict[str, Any] = {}

    if filters.trend_type:
        where.append("trend_type = %(trend_type)s")
        params["trend_type"] = filters.trend_type

    if filters.category:
        where.append("category = %(category)s")
        params["category"] = filters.category

    if filters.keyword:
        kw_like = f"%{filters.keyword}%"
        where.append("(keyword ILIKE %(keyword)s OR keyword_translation ILIKE %(keyword)s)")
        params["keyword"] = kw_like

    if filters.search_volume_min is not None:
        where.append("end_search_volume >= %(search_volume_min)s")
        params["search_volume_min"] = filters.search_volume_min

    if filters.search_volume_max is not None:
        where.append("end_search_volume <= %(search_volume_max)s")
        params["search_volume_max"] = filters.search_volume_max

    if filters.growth_rate_min is not None:
        where.append("search_volume_growth_rate >= %(growth_rate_min)s")
        params["growth_rate_min"] = filters.growth_rate_min

    if filters.growth_rate_max is not None:
        where.append("search_volume_growth_rate <= %(growth_rate_max)s")
        params["growth_rate_max"] = filters.growth_rate_max

    if filters.month_count_min is not None:
        where.append("month_count >= %(month_count_min)s")
        params["month_count_min"] = filters.month_count_min

    if filters.month_count_max is not None:
        where.append("month_count <= %(month_count_max)s")
        params["month_count_max"] = filters.month_count_max

    if filters.ppc_min is not None:
        where.append("ppc_bid_mid >= %(ppc_min)s")
        params["ppc_min"] = filters.ppc_min

    if filters.ppc_max is not None:
        where.append("ppc_bid_mid <= %(ppc_max)s")
        params["ppc_max"] = filters.ppc_max

    if filters.spr_min is not None:
        where.append("spr >= %(spr_min)s")
        params["spr_min"] = filters.spr_min

    if filters.spr_max is not None:
        where.append("spr <= %(spr_max)s")
        params["spr_max"] = filters.spr_max

    return " AND ".join(where), params


def _compare_ctes(base_where_sql: str) -> str:
    return f"""
        WITH span AS (
            SELECT COUNT(DISTINCT data_month)::int AS total_months
            FROM keyword_monthly_metrics m
            WHERE m.data_month BETWEEN %(start_month)s AND %(end_month)s
              AND (%(marketplace)s::text IS NULL OR m.marketplace = %(marketplace)s::text)
        ),
        base AS (
            SELECT
                m.keyword_id,
                m.marketplace,
                k.keyword_normalized AS keyword,
                m.data_month,
                m.keyword_translation,
                m.category,
                m.search_rank,
                m.search_volume,
                m.ppc_bid_mid,
                m.spr,
                m.prev_month_rank,
                m.four_months_ago_rank,
                m.twelve_months_ago_rank,
                (
                    (EXTRACT(YEAR FROM m.data_month)::int * 12 + EXTRACT(MONTH FROM m.data_month)::int)
                    - (EXTRACT(YEAR FROM %(start_month)s::date)::int * 12 + EXTRACT(MONTH FROM %(start_month)s::date)::int)
                    + 1
                )::numeric AS month_idx
            FROM keyword_monthly_metrics m
            JOIN keywords k ON k.id = m.keyword_id
            WHERE {base_where_sql}
        ),
        rolled AS (
            SELECT
                b.keyword_id,
                b.marketplace,
                (ARRAY_AGG(b.keyword ORDER BY b.data_month DESC))[1] AS keyword,
                (ARRAY_AGG(b.keyword_translation ORDER BY b.data_month DESC))[1] AS keyword_translation,
                (ARRAY_AGG(b.category ORDER BY b.data_month DESC))[1] AS category,
                MIN(b.data_month) AS first_month,
                MAX(b.data_month) AS last_month,
                COUNT(*)::int AS month_count,
                MAX(span.total_months)::int AS total_months,
                (ARRAY_AGG(b.search_volume ORDER BY b.data_month ASC))[1] AS start_search_volume,
                (ARRAY_AGG(b.search_volume ORDER BY b.data_month DESC))[1] AS end_search_volume,
                (ARRAY_AGG(b.search_rank ORDER BY b.data_month ASC))[1] AS start_rank,
                (ARRAY_AGG(b.search_rank ORDER BY b.data_month DESC))[1] AS end_rank,
                (ARRAY_AGG(b.ppc_bid_mid ORDER BY b.data_month DESC))[1] AS ppc_bid_mid,
                (ARRAY_AGG(b.spr ORDER BY b.data_month DESC))[1] AS spr,
                (ARRAY_AGG(b.prev_month_rank ORDER BY b.data_month DESC))[1] AS prev_month_rank,
                (ARRAY_AGG(b.four_months_ago_rank ORDER BY b.data_month DESC))[1] AS four_months_ago_rank,
                (ARRAY_AGG(b.twelve_months_ago_rank ORDER BY b.data_month DESC))[1] AS twelve_months_ago_rank,
                JSONB_AGG(
                    JSONB_BUILD_OBJECT(
                        'data_month', b.data_month,
                        'search_rank', b.search_rank,
                        'search_volume', b.search_volume,
                        'ppc_bid_mid', b.ppc_bid_mid,
                        'spr', b.spr
                    )
                    ORDER BY b.data_month
                ) AS monthly,
                AVG(b.search_volume) FILTER (WHERE b.search_volume IS NOT NULL) AS avg_search_volume,
                STDDEV(b.search_volume) FILTER (WHERE b.search_volume IS NOT NULL) AS stddev_search_volume,
                REGR_SLOPE(b.search_volume, b.month_idx) AS volume_slope,
                REGR_R2(b.search_volume, b.month_idx) AS volume_r2
            FROM base b
            CROSS JOIN span
            GROUP BY b.keyword_id, b.marketplace
        ),
        calc AS (
            SELECT
                *,
                CASE
                    WHEN start_search_volume IS NULL OR end_search_volume IS NULL THEN NULL
                    ELSE end_search_volume - start_search_volume
                END AS search_volume_change,
                CASE
                    WHEN start_search_volume IS NULL OR start_search_volume = 0 OR end_search_volume IS NULL THEN NULL
                    ELSE ROUND(((end_search_volume - start_search_volume) / start_search_volume::numeric) * 100, 2)
                END AS search_volume_growth_rate,
                CASE
                    WHEN start_rank IS NULL OR end_rank IS NULL THEN NULL
                    ELSE start_rank - end_rank
                END AS rank_change,
                CASE
                    WHEN avg_search_volume > 0 AND stddev_search_volume IS NOT NULL
                    THEN stddev_search_volume / avg_search_volume
                END AS cv_search_volume,
                total_months - month_count AS gap_count
            FROM rolled
        ),
        calc_base AS (
            SELECT
                c.*,
                pm.search_volume AS prev_month_search_volume,
                ym.search_volume AS yoy_search_volume
            FROM calc c
            LEFT JOIN keyword_monthly_metrics pm
              ON pm.keyword_id = c.keyword_id
             AND pm.marketplace = c.marketplace
             AND pm.data_month = (c.last_month - INTERVAL '1 month')::date
            LEFT JOIN keyword_monthly_metrics ym
              ON ym.keyword_id = c.keyword_id
             AND ym.marketplace = c.marketplace
             AND ym.data_month = (c.last_month - INTERVAL '12 months')::date
        ),
        calc_full AS (
            SELECT
                *,
                CASE
                    WHEN prev_month_search_volume IS NOT NULL AND prev_month_search_volume > 0
                    THEN end_search_volume - prev_month_search_volume
                END AS mom_change,
                CASE
                    WHEN prev_month_search_volume IS NOT NULL AND prev_month_search_volume > 0
                    THEN ROUND(((end_search_volume - prev_month_search_volume) / prev_month_search_volume::numeric) * 100, 2)
                END AS mom_rate,
                CASE
                    WHEN yoy_search_volume IS NOT NULL AND yoy_search_volume > 0
                    THEN end_search_volume - yoy_search_volume
                END AS yoy_change,
                CASE
                    WHEN yoy_search_volume IS NOT NULL AND yoy_search_volume > 0
                    THEN ROUND(((end_search_volume - yoy_search_volume) / yoy_search_volume::numeric) * 100, 2)
                END AS yoy_rate
            FROM calc_base
        ),
        classified AS (
            SELECT
                *,
                CASE
                    WHEN month_count >= 4
                         AND avg_search_volume > 0
                         AND volume_slope > 0
                         AND volume_slope / avg_search_volume > 0.05
                         AND volume_r2 >= 0.25
                        THEN 'rising'
                    WHEN month_count >= 4
                         AND avg_search_volume > 0
                         AND volume_slope < 0
                         AND ABS(volume_slope) / avg_search_volume > 0.05
                         AND volume_r2 >= 0.25
                        THEN 'falling'
                    WHEN month_count >= 5
                         AND avg_search_volume >= 100
                         AND cv_search_volume IS NOT NULL
                         AND cv_search_volume < 0.25
                         AND (volume_slope IS NULL OR ABS(volume_slope) / NULLIF(avg_search_volume, 0) < 0.05)
                        THEN 'stable'
                    WHEN gap_count BETWEEN 1 AND 4
                         AND month_count >= 3
                         AND avg_search_volume >= 100
                         AND (cv_search_volume >= 0.25 OR cv_search_volume IS NULL OR volume_r2 < 0.25)
                        THEN 'seasonal'
                    ELSE 'volatile'
                END AS trend_type,
                CASE
                    WHEN month_count >= 4
                         AND avg_search_volume > 0
                         AND volume_slope > 0
                         AND volume_slope / avg_search_volume > 0.05
                         AND volume_r2 >= 0.25
                        THEN '上升型'
                    WHEN month_count >= 4
                         AND avg_search_volume > 0
                         AND volume_slope < 0
                         AND ABS(volume_slope) / avg_search_volume > 0.05
                         AND volume_r2 >= 0.25
                        THEN '下降型'
                    WHEN month_count >= 5
                         AND avg_search_volume >= 100
                         AND cv_search_volume IS NOT NULL
                         AND cv_search_volume < 0.25
                         AND (volume_slope IS NULL OR ABS(volume_slope) / NULLIF(avg_search_volume, 0) < 0.05)
                        THEN '常年稳定型'
                    WHEN gap_count BETWEEN 1 AND 4
                         AND month_count >= 3
                         AND avg_search_volume >= 100
                         AND (cv_search_volume >= 0.25 OR cv_search_volume IS NULL OR volume_r2 < 0.25)
                        THEN '季节型'
                    ELSE '波动型'
                END AS trend_type_cn
            FROM calc_full
        )
    """


def _month_to_date(value: str | None) -> date | None:
    if not value:
        return None
    text = value.strip()
    if len(text) == 7:
        text = f"{text}-01"
    return date.fromisoformat(text)


def _available_range(conn: psycopg.Connection, marketplace: str | None) -> tuple[date, date]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                MIN(data_month) AS min_month,
                MAX(data_month) AS max_month
            FROM keyword_monthly_metrics
            WHERE (%(marketplace)s::text IS NULL OR marketplace = %(marketplace)s::text)
            """,
            {"marketplace": marketplace},
        )
        row = cur.fetchone()
    if not row or not row["min_month"] or not row["max_month"]:
        raise ValueError("没有可用于横向对比的月份数据")
    return row["min_month"], row["max_month"]


def _resolve_range(conn: psycopg.Connection, filters: KeywordCompareFilters) -> tuple[date, date]:
    """Return (start_month, end_month) for the months dropdown in the UI."""
    min_month, max_month = _available_range(conn, filters.marketplace)
    start_month = _month_to_date(filters.start_month) or min_month
    end_month = _month_to_date(filters.end_month) or max_month
    if start_month > end_month:
        start_month, end_month = end_month, start_month
    return start_month, end_month


def resolve_keyword_compare_range(
    conn: psycopg.Connection, filters: KeywordCompareFilters
) -> tuple[date, date]:
    """Public wrapper: resolve the actual compare date range from filters.

    Falls back to the available min/max months when filters have empty values.
    """
    return _resolve_range(conn, filters)


def _is_full_range(conn: psycopg.Connection, start_month: date, end_month: date, marketplace: str | None) -> bool:
    min_month, max_month = _available_range(conn, marketplace)
    return start_month == min_month and end_month == max_month


def _snapshot_has_range(conn: psycopg.Connection, marketplace: str | None) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM keyword_compare_snapshot
                WHERE (%(marketplace)s::text IS NULL OR marketplace = %(marketplace)s::text)
                LIMIT 1
            ) AS ok
            """,
            {"marketplace": marketplace},
        )
        row = cur.fetchone()
        return bool(row["ok"])


def _source_cte_sql(use_snapshot: bool) -> str:
    if use_snapshot:
        return f"""
            source AS (
                SELECT {SOURCE_COLUMNS}
                FROM keyword_compare_snapshot
                WHERE (%(marketplace)s::text IS NULL OR marketplace = %(marketplace)s::text)
            )
        """
    return f"""
        source AS (
            SELECT {SOURCE_COLUMNS}
            FROM keyword_compare_range_cache
            WHERE start_month = %(start_month)s
              AND end_month = %(end_month)s
              AND marketplace = %(marketplace)s
        )
    """


def _live_source_cte_sql(base_where_sql: str) -> str:
    ctes = _compare_ctes(base_where_sql).lstrip()
    if ctes.upper().startswith("WITH "):
        ctes = ctes[5:]
    return f"""
        {ctes},
        source AS (
            SELECT {SOURCE_COLUMNS}
            FROM classified
        )
    """


def _range_cache_exists(conn: psycopg.Connection, start_month: date, end_month: date, marketplace: str) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM keyword_compare_range_cache
                WHERE start_month = %(start_month)s
                  AND end_month = %(end_month)s
                  AND marketplace = %(marketplace)s
                LIMIT 1
            ) AS ok
            """,
            {"start_month": start_month, "end_month": end_month, "marketplace": marketplace},
        )
        row = cur.fetchone()
        return bool(row["ok"])


def _ensure_range_cache(
    conn: psycopg.Connection,
    filters: KeywordCompareFilters,
    start_month: date,
    end_month: date,
) -> None:
    if not filters.marketplace:
        return
    if _range_cache_exists(conn, start_month, end_month, filters.marketplace):
        return

    params = {
        "start_month": start_month,
        "end_month": end_month,
        "marketplace": filters.marketplace,
    }
    base_where_sql, base_params = _base_where(
        KeywordCompareFilters(
            start_month=str(start_month),
            end_month=str(end_month),
            marketplace=filters.marketplace,
        )
    )
    lock_sql = """
        SELECT pg_advisory_xact_lock(
            hashtextextended(
                'keyword_compare_range_cache:' || %(marketplace)s || ':' || %(start_month)s::text || ':' || %(end_month)s::text,
                0
            )
        )
    """
    insert_sql = f"""
        INSERT INTO keyword_compare_range_cache (
            start_month,
            end_month,
            keyword_id,
            marketplace,
            keyword,
            keyword_translation,
            category,
            first_month,
            last_month,
            month_count,
            total_months,
            start_search_volume,
            end_search_volume,
            search_volume_change,
            search_volume_growth_rate,
            start_rank,
            end_rank,
            rank_change,
            trend_type,
            trend_type_cn,
            ppc_bid_mid,
            spr,
            prev_month_rank,
            four_months_ago_rank,
            twelve_months_ago_rank,
            monthly,
            avg_search_volume,
            stddev_search_volume,
            cv_search_volume,
            volume_slope,
            volume_r2,
            gap_count,
            prev_month_search_volume,
            yoy_search_volume,
            mom_change,
            mom_rate,
            yoy_change,
            yoy_rate
        )
        {_compare_ctes(base_where_sql)}
        SELECT
            %(start_month)s,
            %(end_month)s,
            keyword_id,
            marketplace,
            keyword,
            keyword_translation,
            category,
            first_month,
            last_month,
            month_count,
            total_months,
            start_search_volume,
            end_search_volume,
            search_volume_change,
            search_volume_growth_rate,
            start_rank,
            end_rank,
            rank_change,
            trend_type,
            trend_type_cn,
            ppc_bid_mid,
            spr,
            prev_month_rank,
            four_months_ago_rank,
            twelve_months_ago_rank,
            monthly,
            avg_search_volume,
            stddev_search_volume,
            cv_search_volume,
            volume_slope,
            volume_r2,
            gap_count,
            prev_month_search_volume,
            yoy_search_volume,
            mom_change,
            mom_rate,
            yoy_change,
            yoy_rate
        FROM classified
        ON CONFLICT (start_month, end_month, marketplace, keyword_id) DO UPDATE
        SET
            keyword = EXCLUDED.keyword,
            keyword_translation = EXCLUDED.keyword_translation,
            category = EXCLUDED.category,
            first_month = EXCLUDED.first_month,
            last_month = EXCLUDED.last_month,
            month_count = EXCLUDED.month_count,
            total_months = EXCLUDED.total_months,
            start_search_volume = EXCLUDED.start_search_volume,
            end_search_volume = EXCLUDED.end_search_volume,
            search_volume_change = EXCLUDED.search_volume_change,
            search_volume_growth_rate = EXCLUDED.search_volume_growth_rate,
            start_rank = EXCLUDED.start_rank,
            end_rank = EXCLUDED.end_rank,
            rank_change = EXCLUDED.rank_change,
            trend_type = EXCLUDED.trend_type,
            trend_type_cn = EXCLUDED.trend_type_cn,
            ppc_bid_mid = EXCLUDED.ppc_bid_mid,
            spr = EXCLUDED.spr,
            prev_month_rank = EXCLUDED.prev_month_rank,
            four_months_ago_rank = EXCLUDED.four_months_ago_rank,
            twelve_months_ago_rank = EXCLUDED.twelve_months_ago_rank,
            monthly = EXCLUDED.monthly,
            avg_search_volume = EXCLUDED.avg_search_volume,
            stddev_search_volume = EXCLUDED.stddev_search_volume,
            cv_search_volume = EXCLUDED.cv_search_volume,
            volume_slope = EXCLUDED.volume_slope,
            volume_r2 = EXCLUDED.volume_r2,
            gap_count = EXCLUDED.gap_count,
            prev_month_search_volume = EXCLUDED.prev_month_search_volume,
            yoy_search_volume = EXCLUDED.yoy_search_volume,
            mom_change = EXCLUDED.mom_change,
            mom_rate = EXCLUDED.mom_rate,
            yoy_change = EXCLUDED.yoy_change,
            yoy_rate = EXCLUDED.yoy_rate,
            generated_at = NOW()
    """
    with conn.cursor() as cur:
        cur.execute("SET statement_timeout = '120s'")
        cur.execute(lock_sql, params)
        if _range_cache_exists(conn, start_month, end_month, filters.marketplace):
            conn.commit()
            return
        cur.execute(
            """
            DELETE FROM keyword_compare_range_cache
            WHERE start_month = %(start_month)s
              AND end_month = %(end_month)s
              AND marketplace = %(marketplace)s
            """,
            params,
        )
        cur.execute(insert_sql, {**params, **base_params})
    conn.commit()


def _attach_holiday_tags(
    conn: psycopg.Connection,
    items: list[dict[str, Any]],
    marketplace: str | None,
    range_start: str | None = None,
    range_end: str | None = None,
) -> None:
    """Fetch holiday tags for a batch of keywords and attach them in-place.

    Only returns tags whose trend window falls within [range_start, range_end]
    so that historical tags don't leak into unrelated compare ranges.
    """
    if not items or not marketplace:
        return

    keyword_ids = list({item["keyword_id"] for item in items})
    if not keyword_ids:
        return

    if range_start and range_end:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    keyword_id,
                    holiday_code,
                    holiday_name_cn,
                    confidence,
                    matched_terms,
                    match_sources,
                    trend_year,
                    trend_start_month,
                    trend_end_month,
                    start_volume,
                    end_volume,
                    growth_rate,
                    is_trend_confirmed
                FROM keyword_holiday_tags
                WHERE keyword_id = ANY(%s) AND marketplace = %s
                  AND make_date(trend_year, trend_start_month, 1) >= %s::date
                  AND make_date(trend_year, trend_end_month, 1) <= %s::date
                ORDER BY keyword_id, confidence DESC, holiday_code
                """,
                [keyword_ids, marketplace, range_start, range_end],
            )
            rows = cur.fetchall()
    else:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    keyword_id,
                    holiday_code,
                    holiday_name_cn,
                    confidence,
                    matched_terms,
                    match_sources,
                    trend_year,
                    trend_start_month,
                    trend_end_month,
                    start_volume,
                    end_volume,
                    growth_rate,
                    is_trend_confirmed
                FROM keyword_holiday_tags
                WHERE keyword_id = ANY(%s) AND marketplace = %s
                ORDER BY keyword_id, confidence DESC, holiday_code
                """,
                [keyword_ids, marketplace],
            )
            rows = cur.fetchall()

    tags_by_kid: dict[int, list[dict[str, Any]]] = {}
    for row in rows:
        tags_by_kid.setdefault(row["keyword_id"], []).append({
            "code": row["holiday_code"],
            "name_cn": row["holiday_name_cn"],
            "confidence": row["confidence"],
            "matched_terms": row["matched_terms"],
            "match_sources": row["match_sources"],
            "trend_year": row["trend_year"],
            "trend_start_month": row["trend_start_month"],
            "trend_end_month": row["trend_end_month"],
            "start_volume": row["start_volume"],
            "end_volume": row["end_volume"],
            "growth_rate": row["growth_rate"],
            "is_trend_confirmed": row["is_trend_confirmed"],
        })

    for item in items:
        tags = tags_by_kid.get(item["keyword_id"], [])
        item["holiday_tags"] = tags
        if not tags:
            item["holiday_label"] = None
        else:
            labels: list[str] = []
            for t in tags:
                if t["confidence"] == "confirmed":
                    labels.append(t["name_cn"])
                else:
                    labels.append(f"{t['name_cn']} · 疑似")
            item["holiday_label"] = " / ".join(dict.fromkeys(labels))  # deduplicate while preserving order


def list_keyword_comparisons(
    conn: psycopg.Connection,
    filters: KeywordCompareFilters,
    user_id: int | None = None,
) -> dict[str, Any]:
    start_month, end_month = _resolve_range(conn, filters)
    # Pre-warm range cache for non-full-range queries so subsequent requests are instant
    if not _is_full_range(conn, start_month, end_month, filters.marketplace) and filters.marketplace:
        _ensure_range_cache(conn, filters, start_month, end_month)

    result_where_sql, result_params = _result_where(filters)
    params = {
        **result_params,
        "start_month": start_month,
        "end_month": end_month,
        "marketplace": filters.marketplace,
    }
    use_snapshot = _is_full_range(conn, start_month, end_month, filters.marketplace) and _snapshot_has_range(conn, filters.marketplace)
    use_range_cache = (
        not use_snapshot
        and bool(filters.marketplace)
        and _range_cache_exists(conn, start_month, end_month, filters.marketplace)
    )
    if use_snapshot:
        source_cte = _source_cte_sql(use_snapshot=True)
    elif use_range_cache:
        source_cte = _source_cte_sql(use_snapshot=False)
    else:
        base_where_sql, base_params = _base_where(filters)
        params.update(base_params)
        source_cte = _live_source_cte_sql(base_where_sql)
    exact_total = use_snapshot or use_range_cache

    page = max(filters.page, 1)
    page_size = min(max(filters.page_size, 1), 500)
    offset = (page - 1) * page_size
    query_limit = page_size if exact_total else page_size + 1
    sort_column = SORT_COLUMNS.get(filters.sort_by, "search_volume_growth_rate")
    sort_order = "ASC" if filters.sort_order.lower() == "asc" else "DESC"

    select_sql = f"""
        WITH {source_cte},
        filtered AS (
            SELECT *
            FROM source
            WHERE {result_where_sql}
        ),
        page_rows AS (
            SELECT *
            FROM filtered
            ORDER BY {sort_column} {sort_order} NULLS LAST, end_search_volume DESC NULLS LAST, keyword ASC
            LIMIT %(limit)s OFFSET %(offset)s
        )
        SELECT
            p.keyword_id,
            p.keyword,
            p.keyword_translation,
            p.category,
            p.marketplace,
            p.first_month,
            p.last_month,
            p.start_search_volume,
            p.end_search_volume,
            p.search_volume_change,
            p.search_volume_growth_rate,
            p.start_rank AS start_rank,
            p.end_rank AS end_rank,
            p.rank_change,
            p.month_count,
            p.total_months,
            p.avg_search_volume,
            p.ppc_bid_mid,
            p.spr,
            p.prev_month_rank,
            p.four_months_ago_rank,
            p.twelve_months_ago_rank,
            p.trend_type,
            p.trend_type_cn,
            p.monthly,
            p.mom_change,
            p.mom_rate,
            p.yoy_change,
            p.yoy_rate,
            state.status AS user_status,
            state.priority AS user_priority,
            COALESCE(state.is_favorite, FALSE) AS user_is_favorite,
            state.notes AS user_notes
        FROM page_rows p
        LEFT JOIN keyword_selection_states state
          ON state.keyword_id = p.keyword_id
         AND state.analysis_month = p.last_month
         AND state.marketplace = p.marketplace
         AND state.owner_user_id = %(user_id)s::int
    """

    count_sql = f"""
        WITH {source_cte}
        SELECT COUNT(*) AS total
        FROM source
        WHERE {result_where_sql}
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

        total = None
        if exact_total:
            cur.execute(count_sql, params)
            total = cur.fetchone()["total"]

        cur.execute(
            select_sql,
            {**params, "user_id": user_id, "limit": query_limit, "offset": offset},
        )
        items = cur.fetchall()

    has_more = len(items) > page_size
    if has_more:
        items = items[:page_size]

    for item in items:
        if not item.get("trend_type_cn"):
            item["trend_type_cn"] = TREND_LABELS_CN.get(item["trend_type"], item["trend_type"])

    # Attach holiday tags (filtered to the current compare range)
    _attach_holiday_tags(
        conn, items, filters.marketplace,
        range_start=start_month.isoformat() if start_month else None,
        range_end=end_month.isoformat() if end_month else None,
    )

    if total is None:
        total = offset + len(items) + (1 if has_more else 0)
        total_pages = page + (1 if has_more else 0)
        total_is_estimated = True
        total_label = "lower_bound"
    else:
        total_pages = (total + page_size - 1) // page_size
        has_more = page < total_pages
        total_is_estimated = False
        total_label = "exact"

    return {
        "items": items,
        "months": [{"data_month": month} for month in months],
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": total_pages,
            "total_is_estimated": total_is_estimated,
            "total_label": total_label,
            "has_more": has_more,
        },
    }


def count_keyword_comparisons(conn: psycopg.Connection, filters: KeywordCompareFilters) -> int:
    start_month, end_month = _resolve_range(conn, filters)
    # Pre-warm range cache for non-full-range queries
    if not _is_full_range(conn, start_month, end_month, filters.marketplace) and filters.marketplace:
        _ensure_range_cache(conn, filters, start_month, end_month)

    result_where_sql, result_params = _result_where(filters)
    params = {
        **result_params,
        "start_month": start_month,
        "end_month": end_month,
        "marketplace": filters.marketplace,
    }
    use_snapshot = _is_full_range(conn, start_month, end_month, filters.marketplace) and _snapshot_has_range(conn, filters.marketplace)
    use_range_cache = (
        not use_snapshot
        and bool(filters.marketplace)
        and _range_cache_exists(conn, start_month, end_month, filters.marketplace)
    )
    if use_snapshot:
        source_cte = _source_cte_sql(use_snapshot=True)
    elif use_range_cache:
        source_cte = _source_cte_sql(use_snapshot=False)
    else:
        base_where_sql, base_params = _base_where(filters)
        params.update(base_params)
        source_cte = _live_source_cte_sql(base_where_sql)
    sql = f"""
        WITH {source_cte}
        SELECT COUNT(*) AS total
        FROM source
        WHERE {result_where_sql}
    """
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchone()["total"]


def export_comparisons(
    conn: psycopg.Connection,
    filters: KeywordCompareFilters,
    user_id: int | None = None,
    max_rows: int = 5000,
) -> list[dict[str, Any]]:
    start_month, end_month = _resolve_range(conn, filters)
    use_snapshot = _is_full_range(conn, start_month, end_month, filters.marketplace) and _snapshot_has_range(conn, filters.marketplace)
    if not use_snapshot and filters.marketplace and not _range_cache_exists(conn, start_month, end_month, filters.marketplace):
        _ensure_range_cache(conn, filters, start_month, end_month)

    page_size = 500
    page = 1
    rows: list[dict[str, Any]] = []
    while len(rows) < max_rows:
        result = list_keyword_comparisons(conn, KeywordCompareFilters(
            page=page, page_size=page_size,
            start_month=filters.start_month, end_month=filters.end_month,
            marketplace=filters.marketplace, keyword=filters.keyword,
            category=filters.category, trend_type=filters.trend_type,
            search_volume_min=filters.search_volume_min,
            search_volume_max=filters.search_volume_max,
            growth_rate_min=filters.growth_rate_min,
            growth_rate_max=filters.growth_rate_max,
            month_count_min=filters.month_count_min,
            month_count_max=filters.month_count_max,
            ppc_min=filters.ppc_min, ppc_max=filters.ppc_max,
            spr_min=filters.spr_min, spr_max=filters.spr_max,
            sort_by=filters.sort_by, sort_order=filters.sort_order,
        ), user_id=user_id)
        items = result["items"]
        if not items:
            break
        rows.extend(items)
        if not result["pagination"]["has_more"]:
            break
        page += 1
    return rows[:max_rows]
