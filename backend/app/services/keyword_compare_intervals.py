from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

import psycopg


INTERVAL_INSERT_COLUMNS = """
    interval_code,
    interval_name,
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
"""


@dataclass(frozen=True)
class CompareInterval:
    code: str
    name: str
    start_month: date
    end_month: date


def refresh_interval_snapshot(
    conn: psycopg.Connection,
    interval: CompareInterval,
    *,
    marketplace: str,
    statement_timeout: str = "600s",
) -> int:
    """Populate keyword_compare_interval_snapshot for one interval.

    Joins the full-range keyword_compare_snapshot with jsonb_array_elements
    to extract only the months within the interval window. Computes all
    derived columns (growth rate, mom/yoy, trend type) from the sub-range.
    """
    sql = f"""
        INSERT INTO keyword_compare_interval_snapshot ({INTERVAL_INSERT_COLUMNS})
        WITH interval_rows AS (
            SELECT
                s.keyword_id,
                s.marketplace,
                s.keyword,
                s.keyword_translation,
                s.category,
                w.first_month,
                w.last_month,
                w.month_count,
                w.total_months,
                w.start_search_volume,
                w.end_search_volume,
                CASE
                    WHEN w.start_search_volume IS NULL OR w.end_search_volume IS NULL THEN NULL
                    ELSE w.end_search_volume - w.start_search_volume
                END AS search_volume_change,
                CASE
                    WHEN w.start_search_volume IS NULL OR w.start_search_volume = 0 OR w.end_search_volume IS NULL THEN NULL
                    ELSE ROUND(((w.end_search_volume - w.start_search_volume) / w.start_search_volume::numeric) * 100, 2)
                END AS search_volume_growth_rate,
                w.start_rank,
                w.end_rank,
                CASE
                    WHEN w.start_rank IS NULL OR w.end_rank IS NULL THEN NULL
                    ELSE w.start_rank - w.end_rank
                END AS rank_change,
                s.trend_type,
                s.trend_type_cn,
                w.ppc_bid_mid,
                w.spr,
                w.prev_month_rank,
                w.four_months_ago_rank,
                w.twelve_months_ago_rank,
                w.monthly,
                w.avg_search_volume,
                w.stddev_search_volume,
                CASE
                    WHEN w.avg_search_volume > 0 AND w.stddev_search_volume IS NOT NULL
                    THEN w.stddev_search_volume / w.avg_search_volume
                END AS cv_search_volume,
                w.volume_slope,
                w.volume_r2,
                w.total_months - w.month_count AS gap_count,
                w.prev_month_search_volume,
                NULL::numeric AS yoy_search_volume,
                CASE
                    WHEN w.prev_month_search_volume IS NOT NULL AND w.prev_month_search_volume > 0
                    THEN w.end_search_volume - w.prev_month_search_volume
                END AS mom_change,
                CASE
                    WHEN w.prev_month_search_volume IS NOT NULL AND w.prev_month_search_volume > 0
                    THEN ROUND(((w.end_search_volume - w.prev_month_search_volume) / w.prev_month_search_volume::numeric) * 100, 2)
                END AS mom_rate,
                NULL::numeric AS yoy_change,
                NULL::numeric AS yoy_rate
            FROM keyword_compare_snapshot s
            CROSS JOIN LATERAL (
                SELECT
                    MIN(m.month_date) AS first_month,
                    MAX(m.month_date) AS last_month,
                    COUNT(*)::int AS month_count,
                    (
                        (
                            EXTRACT(YEAR FROM %(end_month)s::date)::int * 12
                            + EXTRACT(MONTH FROM %(end_month)s::date)::int
                        )
                        - (
                            EXTRACT(YEAR FROM %(start_month)s::date)::int * 12
                            + EXTRACT(MONTH FROM %(start_month)s::date)::int
                        )
                        + 1
                    )::int AS total_months,
                    (ARRAY_AGG(m.search_volume ORDER BY m.month_date ASC))[1] AS start_search_volume,
                    (ARRAY_AGG(m.search_volume ORDER BY m.month_date DESC))[1] AS end_search_volume,
                    (ARRAY_AGG(m.search_rank ORDER BY m.month_date ASC))[1] AS start_rank,
                    (ARRAY_AGG(m.search_rank ORDER BY m.month_date DESC))[1] AS end_rank,
                    (ARRAY_AGG(m.ppc_bid_mid ORDER BY m.month_date DESC))[1] AS ppc_bid_mid,
                    (ARRAY_AGG(m.spr ORDER BY m.month_date DESC))[1] AS spr,
                    (ARRAY_AGG(m.prev_month_rank ORDER BY m.month_date DESC))[1] AS prev_month_rank,
                    (ARRAY_AGG(m.four_months_ago_rank ORDER BY m.month_date DESC))[1] AS four_months_ago_rank,
                    (ARRAY_AGG(m.twelve_months_ago_rank ORDER BY m.month_date DESC))[1] AS twelve_months_ago_rank,
                    JSONB_AGG(m.item ORDER BY m.month_date) AS monthly,
                    AVG(m.search_volume) FILTER (WHERE m.search_volume IS NOT NULL) AS avg_search_volume,
                    STDDEV(m.search_volume) FILTER (WHERE m.search_volume IS NOT NULL) AS stddev_search_volume,
                    REGR_SLOPE(m.search_volume, m.month_idx) AS volume_slope,
                    REGR_R2(m.search_volume, m.month_idx) AS volume_r2,
                    MAX(m.search_volume) FILTER (
                        WHERE m.month_date = (%(end_month)s::date - INTERVAL '1 month')::date
                    ) AS prev_month_search_volume
                FROM (
                    SELECT
                        item,
                        (item->>'data_month')::date AS month_date,
                        NULLIF(item->>'search_rank', 'null')::int AS search_rank,
                        NULLIF(item->>'search_volume', 'null')::numeric AS search_volume,
                        NULLIF(item->>'ppc_bid_mid', 'null')::numeric AS ppc_bid_mid,
                        NULLIF(item->>'spr', 'null')::int AS spr,
                        NULLIF(item->>'prev_month_rank', 'null')::int AS prev_month_rank,
                        NULLIF(item->>'four_months_ago_rank', 'null')::int AS four_months_ago_rank,
                        NULLIF(item->>'twelve_months_ago_rank', 'null')::int AS twelve_months_ago_rank,
                        (
                            (
                                EXTRACT(YEAR FROM (item->>'data_month')::date)::int * 12
                                + EXTRACT(MONTH FROM (item->>'data_month')::date)::int
                            )
                            - (
                                EXTRACT(YEAR FROM %(start_month)s::date)::int * 12
                                + EXTRACT(MONTH FROM %(start_month)s::date)::int
                            )
                            + 1
                        )::numeric AS month_idx
                    FROM jsonb_array_elements(s.monthly) AS month_items(item)
                    WHERE (item->>'data_month')::date BETWEEN %(start_month)s AND %(end_month)s
                ) m
            ) w
            WHERE s.marketplace = %(marketplace)s
              AND w.month_count > 0
        )
        SELECT
            %(interval_code)s,
            %(interval_name)s,
            %(start_month)s,
            %(end_month)s,
            ir.keyword_id,
            ir.marketplace,
            ir.keyword,
            ir.keyword_translation,
            ir.category,
            ir.first_month,
            ir.last_month,
            ir.month_count,
            ir.total_months,
            ir.start_search_volume,
            ir.end_search_volume,
            ir.search_volume_change,
            ir.search_volume_growth_rate,
            ir.start_rank,
            ir.end_rank,
            ir.rank_change,
            ir.trend_type,
            ir.trend_type_cn,
            ir.ppc_bid_mid,
            ir.spr,
            ir.prev_month_rank,
            ir.four_months_ago_rank,
            ir.twelve_months_ago_rank,
            ir.monthly,
            ir.avg_search_volume,
            ir.stddev_search_volume,
            ir.cv_search_volume,
            ir.volume_slope,
            ir.volume_r2,
            ir.gap_count,
            ir.prev_month_search_volume,
            ir.yoy_search_volume,
            ir.mom_change,
            ir.mom_rate,
            ir.yoy_change,
            ir.yoy_rate
        FROM interval_rows ir
    """
    params: dict[str, Any] = {
        "interval_code": interval.code,
        "interval_name": interval.name,
        "start_month": interval.start_month,
        "end_month": interval.end_month,
        "marketplace": marketplace,
    }

    with conn.cursor() as cur:
        cur.execute(f"SET LOCAL statement_timeout = '{statement_timeout}'")
        cur.execute(
            """
            DELETE FROM keyword_compare_interval_snapshot
            WHERE interval_code = %(interval_code)s
              AND marketplace = %(marketplace)s
              AND start_month = %(start_month)s
              AND end_month = %(end_month)s
            """,
            params,
        )
        cur.execute(sql, params)
        inserted = cur.rowcount
        cur.execute("ANALYZE keyword_compare_interval_snapshot")
    conn.commit()
    return inserted
