from __future__ import annotations

import argparse

import psycopg

from common import add_months, get_database_url, parse_month


TREND_SQL = """
WITH current_month AS (
    SELECT *
    FROM keyword_monthly_metrics
    WHERE data_month = %(analysis_month)s
      AND marketplace = %(marketplace)s
),
previous_month AS (
    SELECT *
    FROM keyword_monthly_metrics
    WHERE data_month = %(prev_month)s
      AND marketplace = %(marketplace)s
),
avg_3m AS (
    SELECT
        keyword_id,
        AVG(search_rank) AS avg_rank_3m,
        AVG(search_volume) AS avg_search_volume_3m
    FROM keyword_monthly_metrics
    WHERE data_month >= %(three_month_start)s
      AND data_month < %(analysis_month)s
      AND marketplace = %(marketplace)s
    GROUP BY keyword_id
),
avg_6m AS (
    SELECT
        keyword_id,
        AVG(search_rank) AS avg_rank_6m,
        AVG(search_volume) AS avg_search_volume_6m
    FROM keyword_monthly_metrics
    WHERE data_month >= %(six_month_start)s
      AND data_month < %(analysis_month)s
      AND marketplace = %(marketplace)s
    GROUP BY keyword_id
),
yoy AS (
    SELECT *
    FROM keyword_monthly_metrics
    WHERE data_month = %(yoy_month)s
      AND marketplace = %(marketplace)s
)
INSERT INTO keyword_monthly_trends (
    keyword_id,
    analysis_month,
    marketplace,
    prev_month_rank,
    current_rank,
    rank_change,
    rank_change_rate,
    prev_month_search_volume,
    current_search_volume,
    search_volume_change,
    search_volume_growth_rate,
    avg_rank_3m,
    avg_search_volume_3m,
    avg_rank_6m,
    avg_search_volume_6m,
    yoy_rank,
    yoy_search_volume,
    yoy_growth_rate,
    trend_label
)
SELECT
    c.keyword_id,
    %(analysis_month)s,
    c.marketplace,
    p.search_rank,
    c.search_rank,
    CASE WHEN p.search_rank IS NULL OR c.search_rank IS NULL THEN NULL ELSE p.search_rank - c.search_rank END,
    CASE
        WHEN p.search_rank IS NULL OR p.search_rank = 0 OR c.search_rank IS NULL THEN NULL
        ELSE (p.search_rank - c.search_rank)::NUMERIC / p.search_rank
    END,
    p.search_volume,
    c.search_volume,
    CASE WHEN p.search_volume IS NULL OR c.search_volume IS NULL THEN NULL ELSE c.search_volume - p.search_volume END,
    CASE
        WHEN p.search_volume IS NULL OR p.search_volume = 0 OR c.search_volume IS NULL THEN NULL
        ELSE (c.search_volume - p.search_volume) / p.search_volume
    END,
    a3.avg_rank_3m,
    a3.avg_search_volume_3m,
    a6.avg_rank_6m,
    a6.avg_search_volume_6m,
    y.search_rank,
    y.search_volume,
    CASE
        WHEN y.search_volume IS NULL OR y.search_volume = 0 OR c.search_volume IS NULL THEN NULL
        ELSE (c.search_volume - y.search_volume) / y.search_volume
    END,
    CASE
        WHEN p.keyword_id IS NULL THEN 'new'
        WHEN p.search_volume IS NOT NULL AND c.search_volume IS NOT NULL
             AND p.search_rank IS NOT NULL AND c.search_rank IS NOT NULL
             AND c.search_volume > p.search_volume
             AND c.search_rank < p.search_rank THEN 'rising'
        WHEN p.search_volume IS NOT NULL AND c.search_volume IS NOT NULL
             AND p.search_rank IS NOT NULL AND c.search_rank IS NOT NULL
             AND c.search_volume > p.search_volume
             AND c.search_rank > p.search_rank THEN 'volume_up_rank_down'
        WHEN p.search_volume IS NOT NULL AND c.search_volume IS NOT NULL
             AND p.search_rank IS NOT NULL AND c.search_rank IS NOT NULL
             AND c.search_volume < p.search_volume
             AND c.search_rank < p.search_rank THEN 'rank_up_volume_down'
        WHEN p.search_volume IS NOT NULL AND c.search_volume IS NOT NULL
             AND p.search_rank IS NOT NULL AND c.search_rank IS NOT NULL
             AND c.search_volume < p.search_volume
             AND c.search_rank > p.search_rank THEN 'falling'
        WHEN p.search_volume IS NOT NULL AND c.search_volume IS NOT NULL AND c.search_volume > p.search_volume THEN 'volume_up'
        WHEN p.search_volume IS NOT NULL AND c.search_volume IS NOT NULL AND c.search_volume < p.search_volume THEN 'volume_down'
        WHEN p.search_rank IS NOT NULL AND c.search_rank IS NOT NULL AND c.search_rank < p.search_rank THEN 'rank_up'
        WHEN p.search_rank IS NOT NULL AND c.search_rank IS NOT NULL AND c.search_rank > p.search_rank THEN 'rank_down'
        ELSE 'stable'
    END
FROM current_month c
LEFT JOIN previous_month p ON p.keyword_id = c.keyword_id
LEFT JOIN avg_3m a3 ON a3.keyword_id = c.keyword_id
LEFT JOIN avg_6m a6 ON a6.keyword_id = c.keyword_id
LEFT JOIN yoy y ON y.keyword_id = c.keyword_id
;
"""


def build_params(analysis_month, marketplace: str) -> dict:
    return {
        "analysis_month": analysis_month,
        "marketplace": marketplace,
        "prev_month": add_months(analysis_month, -1),
        "three_month_start": add_months(analysis_month, -3),
        "six_month_start": add_months(analysis_month, -6),
        "yoy_month": add_months(analysis_month, -12),
    }


def calculate_month(conn: psycopg.Connection, analysis_month, marketplace: str) -> None:
    params = build_params(analysis_month, marketplace)
    with conn.cursor() as cur:
        cur.execute(
            """
            DELETE FROM keyword_ops_monthly
            WHERE analysis_month = %(analysis_month)s
              AND marketplace = %(marketplace)s
            """,
            params,
        )
        cur.execute(
            """
            DELETE FROM keyword_monthly_trends
            WHERE analysis_month = %(analysis_month)s
              AND marketplace = %(marketplace)s
            """,
            params,
        )
        cur.execute(TREND_SQL, params)
        cur.execute(OPS_SQL, params)


def get_imported_months(
    conn: psycopg.Connection,
    marketplace: str,
    from_month=None,
    to_month=None,
    year: int | None = None,
) -> list:
    filters = ["marketplace = %s"]
    params: list = [marketplace]
    if from_month is not None:
        filters.append("data_month >= %s")
        params.append(from_month)
    if to_month is not None:
        filters.append("data_month <= %s")
        params.append(to_month)
    if year is not None:
        filters.append("EXTRACT(YEAR FROM data_month) = %s")
        params.append(year)

    where_sql = " AND ".join(filters)
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT DISTINCT data_month
            FROM keyword_monthly_metrics
            WHERE {where_sql}
            ORDER BY data_month
            """,
            params,
        )
        return [row[0] for row in cur.fetchall()]


OPS_SQL = """
INSERT INTO keyword_ops_monthly (
    keyword_id,
    keyword,
    analysis_month,
    marketplace,
    category,
    search_rank,
    search_volume,
    click_share,
    conversion_share,
    rank_change_mom,
    volume_change_mom,
    volume_growth_rate_mom,
    avg_rank_3m,
    avg_volume_3m,
    avg_rank_6m,
    avg_volume_6m,
    yoy_growth_rate,
    trend_label,
    keyword_level,
    lifecycle_stage,
    opportunity_score,
    competition_score,
    conversion_score,
    recommended_action,
    operation_tag,
    top1_asin,
    top2_asin,
    top3_asin
)
SELECT
    m.keyword_id,
    k.keyword_normalized,
    %(analysis_month)s,
    m.marketplace,
    m.category,
    m.search_rank,
    m.search_volume,
    m.click_share,
    m.conversion_share,
    t.rank_change,
    t.search_volume_change,
    t.search_volume_growth_rate,
    t.avg_rank_3m,
    t.avg_search_volume_3m,
    t.avg_rank_6m,
    t.avg_search_volume_6m,
    t.yoy_growth_rate,
    t.trend_label,
    CASE
        WHEN m.search_rank <= 10000 THEN 'core'
        WHEN t.trend_label = 'rising' THEN 'growth'
        WHEN k.word_count >= 4 THEN 'long_tail'
        ELSE 'low_value'
    END,
    t.trend_label,
    LEAST(100, GREATEST(0,
        COALESCE(30 * LEAST(1, m.search_volume / 10000.0), 0)
        + COALESCE(30 * LEAST(1, GREATEST(t.search_volume_growth_rate, 0)), 0)
        + COALESCE(25 * LEAST(1, m.conversion_share / 0.2), 0)
        + COALESCE(15 * CASE WHEN m.search_rank > 50000 THEN 1 ELSE 0.5 END, 0)
    )),
    LEAST(100, GREATEST(0,
        COALESCE(60 * LEAST(1, m.click_share / 0.5), 0)
        + COALESCE(40 * CASE WHEN ABS(COALESCE(t.rank_change, 0)) < 1000 THEN 1 ELSE 0.5 END, 0)
    )),
    LEAST(100, GREATEST(0, COALESCE(100 * LEAST(1, m.conversion_share / 0.2), 0))),
    CASE
        WHEN t.trend_label = 'new' THEN 'add_to_watchlist'
        WHEN t.trend_label = 'rising' AND m.conversion_share >= 0.05 THEN 'add_to_ads'
        WHEN t.trend_label = 'falling' THEN 'observe'
        WHEN m.conversion_share >= 0.1 THEN 'add_to_listing'
        ELSE 'observe'
    END,
    CASE
        WHEN m.conversion_share >= 0.1 THEN 'high_conversion'
        WHEN t.trend_label = 'new' THEN 'new_opportunity'
        WHEN t.trend_label = 'rising' THEN 'growth'
        ELSE 'observe'
    END,
    m.top1_asin,
    m.top2_asin,
    m.top3_asin
FROM keyword_monthly_metrics m
JOIN keywords k ON k.id = m.keyword_id
JOIN keyword_monthly_trends t
  ON t.keyword_id = m.keyword_id
 AND t.analysis_month = %(analysis_month)s
 AND t.marketplace = m.marketplace
WHERE m.data_month = %(analysis_month)s
  AND m.marketplace = %(marketplace)s
;
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Calculate monthly trends and ops table.")
    parser.add_argument("--analysis-month", help="Analysis month, format YYYY-MM.")
    parser.add_argument("--all", action="store_true", help="Recalculate all imported months in chronological order.")
    parser.add_argument("--from-month", help="Optional start month for --all, format YYYY-MM.")
    parser.add_argument("--to-month", help="Optional end month for --all, format YYYY-MM.")
    parser.add_argument("--year", type=int, help="Optional year filter for --all, for example 2026.")
    parser.add_argument("--marketplace", default="US")
    parser.add_argument("--skip-cache-refresh", action="store_true",
                        help="Skip refreshing the product-selection cache table after trend calculation.")
    args = parser.parse_args()

    if not args.all and not args.analysis_month:
        parser.error("Either --analysis-month or --all is required.")
    if args.all and args.analysis_month:
        parser.error("--analysis-month cannot be used together with --all.")

    with psycopg.connect(get_database_url()) as conn:
        # Resolve the list of months to process once.
        if args.all:
            months = get_imported_months(
                conn,
                args.marketplace,
                parse_month(args.from_month) if args.from_month else None,
                parse_month(args.to_month) if args.to_month else None,
                args.year,
            )
            if not months:
                raise RuntimeError("No imported months found for the selected filters.")
        else:
            months = [parse_month(args.analysis_month)]

        # Step 1 — trend + ops calculation.
        for month in months:
            calculate_month(conn, month, args.marketplace)
            conn.commit()
            print(f"Calculated trends and ops table for {month:%Y-%m}.", flush=True)

        # Step 2 — refresh the product-selection cache table so the API immediately
        # serves fresh data without hitting the expensive real-time view.
        if not args.skip_cache_refresh:
            print("Refreshing product-selection cache table ...", flush=True)
            from app.services.product_selection_cache import refresh_cache
            for month in months:
                row_count = refresh_cache(
                    conn,
                    analysis_month=month.isoformat(),
                    marketplace=args.marketplace,
                )
                conn.commit()
                print(f"  Refreshed {month:%Y-%m} {args.marketplace}: {row_count} rows.", flush=True)
            print("Cache refresh done.", flush=True)

        # Step 3 — refresh the keyword compare snapshot so the horizontal
        # compare module serves pre-computed data instead of running heavy
        # window-function queries across all months in real time.
        if not args.skip_cache_refresh:
            print("Refreshing keyword compare snapshot ...", flush=True)
            from app.services.keyword_compare_snapshot import refresh_compare_snapshot
            row_count = refresh_compare_snapshot(conn, marketplace=args.marketplace)
            conn.commit()
            print(f"  Refreshed {args.marketplace} compare snapshot: {row_count} rows.", flush=True)


if __name__ == "__main__":
    main()
