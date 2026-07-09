from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

import psycopg


SCENARIO_INSERT_COLUMNS = """
    scenario_code,
    scenario_name,
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
class CompareScenario:
    code: str
    name: str
    start_month: date
    end_month: date
    holiday_code: str | None = None


def _date_from_window(year: int, month: int) -> date:
    return date(year, month, 1)


def holiday_scenarios_for_marketplace(conn: psycopg.Connection, marketplace: str) -> list[CompareScenario]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                holiday_code,
                holiday_name_cn,
                trend_year,
                trend_start_month,
                trend_end_month,
                COUNT(*) AS keyword_count
            FROM keyword_holiday_tags
            WHERE marketplace = %s
              AND holiday_code IN ('christmas', 'halloween')
              AND confidence = 'confirmed'
            GROUP BY holiday_code, holiday_name_cn, trend_year, trend_start_month, trend_end_month
            HAVING COUNT(*) > 0
            ORDER BY holiday_code, trend_year
            """,
            [marketplace],
        )
        rows = cur.fetchall()

    scenarios: list[CompareScenario] = []
    for row in rows:
        code = row["holiday_code"]
        year = row["trend_year"]
        start_month = _date_from_window(year, row["trend_start_month"])
        end_year = year if row["trend_end_month"] >= row["trend_start_month"] else year + 1
        end_month = _date_from_window(end_year, row["trend_end_month"])
        scenarios.append(
            CompareScenario(
                code=code,
                name=row["holiday_name_cn"],
                start_month=start_month,
                end_month=end_month,
                holiday_code=code,
            )
        )
    return scenarios


def refresh_compare_scenario(
    conn: psycopg.Connection,
    scenario: CompareScenario,
    *,
    marketplace: str,
    statement_timeout: str = "300s",
) -> int:
    sql = f"""
        INSERT INTO keyword_compare_scenario_snapshot ({SCENARIO_INSERT_COLUMNS})
        WITH tagged AS (
            SELECT ht.keyword_id, ht.marketplace
            FROM keyword_holiday_tags ht
            WHERE ht.marketplace = %(marketplace)s
              AND ht.holiday_code = %(holiday_code)s
              AND ht.confidence = 'confirmed'
              AND make_date(ht.trend_year, ht.trend_start_month, 1) = %(start_month)s
              AND make_date(ht.trend_year, ht.trend_end_month, 1) = %(end_month)s
        ),
        scenario_rows AS (
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
            FROM tagged t
            JOIN keyword_compare_snapshot s
              ON s.keyword_id = t.keyword_id
             AND s.marketplace = t.marketplace
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
            WHERE w.month_count > 0
        )
        SELECT
            %(scenario_code)s,
            %(scenario_name)s,
            %(start_month)s,
            %(end_month)s,
            sr.keyword_id,
            sr.marketplace,
            sr.keyword,
            sr.keyword_translation,
            sr.category,
            sr.first_month,
            sr.last_month,
            sr.month_count,
            sr.total_months,
            sr.start_search_volume,
            sr.end_search_volume,
            sr.search_volume_change,
            sr.search_volume_growth_rate,
            sr.start_rank,
            sr.end_rank,
            sr.rank_change,
            sr.trend_type,
            sr.trend_type_cn,
            sr.ppc_bid_mid,
            sr.spr,
            sr.prev_month_rank,
            sr.four_months_ago_rank,
            sr.twelve_months_ago_rank,
            sr.monthly,
            sr.avg_search_volume,
            sr.stddev_search_volume,
            sr.cv_search_volume,
            sr.volume_slope,
            sr.volume_r2,
            sr.gap_count,
            sr.prev_month_search_volume,
            sr.yoy_search_volume,
            sr.mom_change,
            sr.mom_rate,
            sr.yoy_change,
            sr.yoy_rate
        FROM scenario_rows sr
    """
    params: dict[str, Any] = {
        "scenario_code": scenario.code,
        "scenario_name": scenario.name,
        "start_month": scenario.start_month,
        "end_month": scenario.end_month,
        "marketplace": marketplace,
        "holiday_code": scenario.holiday_code,
    }

    with conn.cursor() as cur:
        cur.execute(f"SET LOCAL statement_timeout = '{statement_timeout}'")
        cur.execute(
            """
            DELETE FROM keyword_compare_scenario_snapshot
            WHERE scenario_code = %(scenario_code)s
              AND marketplace = %(marketplace)s
              AND start_month = %(start_month)s
              AND end_month = %(end_month)s
            """,
            params,
        )
        cur.execute(sql, params)
        inserted = cur.rowcount
        cur.execute("ANALYZE keyword_compare_scenario_snapshot")
    conn.commit()
    return inserted


def refresh_holiday_compare_scenarios(
    conn: psycopg.Connection,
    *,
    marketplace: str,
    statement_timeout: str = "300s",
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for scenario in holiday_scenarios_for_marketplace(conn, marketplace):
        started = scenario.start_month.isoformat()
        ended = scenario.end_month.isoformat()
        try:
            row_count = refresh_compare_scenario(
                conn,
                scenario,
                marketplace=marketplace,
                statement_timeout=statement_timeout,
            )
            results.append({
                "scenario_code": scenario.code,
                "start_month": started,
                "end_month": ended,
                "rows": row_count,
                "ok": True,
            })
        except Exception as exc:
            conn.rollback()
            results.append({
                "scenario_code": scenario.code,
                "start_month": started,
                "end_month": ended,
                "rows": 0,
                "ok": False,
                "error": str(exc),
            })
    return results
