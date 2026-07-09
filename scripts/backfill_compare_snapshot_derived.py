from __future__ import annotations

import argparse

import psycopg

from common import get_database_url


def backfill_compare_snapshot_derived(conn: psycopg.Connection, marketplace: str) -> None:
    params = {"marketplace": marketplace}
    with conn.cursor() as cur:
        cur.execute("SET statement_timeout = 0")
        cur.execute("SET lock_timeout = '30s'")

        print("Updating growth and rank derived fields ...", flush=True)
        cur.execute(
            """
            UPDATE keyword_compare_snapshot s
            SET
                search_volume_change = CASE
                    WHEN start_search_volume IS NULL OR end_search_volume IS NULL
                    THEN NULL
                    ELSE end_search_volume - start_search_volume
                END,
                search_volume_growth_rate = CASE
                    WHEN start_search_volume IS NULL OR start_search_volume = 0
                      OR end_search_volume IS NULL
                    THEN NULL
                    ELSE ROUND(((end_search_volume - start_search_volume) / start_search_volume::numeric) * 100, 2)
                END,
                rank_change = CASE
                    WHEN start_rank IS NULL OR end_rank IS NULL
                    THEN NULL
                    ELSE start_rank - end_rank
                END
            WHERE marketplace = %(marketplace)s
            """,
            params,
        )
        print(f"  {cur.rowcount} rows updated.", flush=True)
        conn.commit()

        print("Updating previous-month and YoY source volumes from monthly JSON ...", flush=True)
        cur.execute(
            """
            UPDATE keyword_compare_snapshot s
            SET
                prev_month_search_volume = (
                    SELECT (elem->>'search_volume')::numeric
                    FROM jsonb_array_elements(s.monthly) elem
                    WHERE (elem->>'data_month')::date = (s.last_month - INTERVAL '1 month')::date
                    LIMIT 1
                ),
                yoy_search_volume = (
                    SELECT (elem->>'search_volume')::numeric
                    FROM jsonb_array_elements(s.monthly) elem
                    WHERE (elem->>'data_month')::date = (s.last_month - INTERVAL '12 months')::date
                    LIMIT 1
                )
            WHERE marketplace = %(marketplace)s
            """,
            params,
        )
        print(f"  {cur.rowcount} rows updated.", flush=True)
        conn.commit()

        print("Updating MoM and YoY derived fields ...", flush=True)
        cur.execute(
            """
            UPDATE keyword_compare_snapshot
            SET
                mom_change = CASE
                    WHEN prev_month_search_volume IS NOT NULL AND prev_month_search_volume > 0
                    THEN end_search_volume - prev_month_search_volume
                END,
                mom_rate = CASE
                    WHEN prev_month_search_volume IS NOT NULL AND prev_month_search_volume > 0
                    THEN ROUND(((end_search_volume - prev_month_search_volume) / prev_month_search_volume::numeric) * 100, 2)
                END,
                yoy_change = CASE
                    WHEN yoy_search_volume IS NOT NULL AND yoy_search_volume > 0
                    THEN end_search_volume - yoy_search_volume
                END,
                yoy_rate = CASE
                    WHEN yoy_search_volume IS NOT NULL AND yoy_search_volume > 0
                    THEN ROUND(((end_search_volume - yoy_search_volume) / yoy_search_volume::numeric) * 100, 2)
                END
            WHERE marketplace = %(marketplace)s
            """,
            params,
        )
        print(f"  {cur.rowcount} rows updated.", flush=True)
        conn.commit()

        print("Computing statistical fields from monthly history ...", flush=True)
        cur.execute("DROP TABLE IF EXISTS _compare_snapshot_stats")
        cur.execute(
            """
            CREATE TEMP TABLE _compare_snapshot_stats AS
            WITH unnested AS (
                SELECT
                    s.keyword_id,
                    s.marketplace,
                    s.total_months,
                    (elem->>'search_volume')::numeric AS search_volume,
                    ROW_NUMBER() OVER (
                        PARTITION BY s.keyword_id, s.marketplace
                        ORDER BY (elem->>'data_month')::date
                    ) AS month_idx
                FROM keyword_compare_snapshot s
                CROSS JOIN LATERAL jsonb_array_elements(s.monthly) AS elem
                WHERE s.marketplace = %(marketplace)s
            ),
            stats AS (
                SELECT
                    keyword_id,
                    marketplace,
                    MAX(total_months) AS total_months,
                    COUNT(*) FILTER (WHERE search_volume IS NOT NULL) AS actual_count,
                    AVG(search_volume) FILTER (WHERE search_volume IS NOT NULL) AS avg_vol,
                    STDDEV(search_volume) FILTER (WHERE search_volume IS NOT NULL) AS stddev_vol,
                    REGR_SLOPE(search_volume, month_idx) AS vol_slope,
                    REGR_R2(search_volume, month_idx) AS vol_r2
                FROM unnested
                GROUP BY keyword_id, marketplace
            )
            SELECT *
            FROM stats
            """,
            params,
        )
        cur.execute(
            """
            CREATE INDEX _compare_snapshot_stats_lookup
            ON _compare_snapshot_stats (keyword_id, marketplace)
            """
        )
        cur.execute("ANALYZE _compare_snapshot_stats")
        cur.execute(
            """
            UPDATE keyword_compare_snapshot s
            SET
                avg_search_volume = stats.avg_vol,
                stddev_search_volume = stats.stddev_vol,
                cv_search_volume = CASE
                    WHEN stats.avg_vol > 0 THEN stats.stddev_vol / stats.avg_vol
                END,
                volume_slope = stats.vol_slope,
                volume_r2 = stats.vol_r2,
                gap_count = stats.total_months - stats.actual_count
            FROM _compare_snapshot_stats stats
            WHERE s.keyword_id = stats.keyword_id
              AND s.marketplace = stats.marketplace
              AND s.marketplace = %(marketplace)s
            """,
            params,
        )
        print(f"  {cur.rowcount} rows updated.", flush=True)
        conn.commit()

        print("Reclassifying trend types ...", flush=True)
        cur.execute(
            """
            UPDATE keyword_compare_snapshot
            SET
                trend_type = CASE
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
                END,
                trend_type_cn = CASE
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
                END,
                refreshed_at = NOW()
            WHERE marketplace = %(marketplace)s
            """,
            params,
        )
        print(f"  {cur.rowcount} rows updated.", flush=True)
        conn.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill derived fields in keyword_compare_snapshot.")
    parser.add_argument("--marketplace", default="UK")
    args = parser.parse_args()

    with psycopg.connect(get_database_url()) as conn:
        backfill_compare_snapshot_derived(conn, args.marketplace)


if __name__ == "__main__":
    main()
