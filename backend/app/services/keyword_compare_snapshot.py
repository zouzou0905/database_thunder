"""Pre-computed snapshot for the keyword horizontal compare module.

The compare query aggregates keyword_monthly_metrics across multiple months
with window functions, JSONB_AGG, and correlated EXISTS subqueries — far too
heavy for real-time API use.  This module mirrors the product-selection cache
pattern: a materialized table refreshed after each trend calculation run.

Classification (5-category system, based on ALL months of data):
    rising   — clear upward trend (≥4 data points, positive slope, R² ≥ 0.25)
    falling  — clear downward trend (≥4 data points, negative slope, R² ≥ 0.25)
    stable   — appears in most months (≥5), low CV (<0.25), no strong trend
    seasonal — gappy pattern (1-4 missing months), irregular but not rare
    volatile — everything else that doesn't fit the above
"""

from __future__ import annotations

import psycopg


def refresh_compare_snapshot(
    conn: psycopg.Connection,
    *,
    marketplace: str,
) -> int:
    """Rebuild the keyword compare snapshot for the given marketplace.

    Uses a multi-step approach with a temp table to avoid expensive single-query
    window functions that would time out on large datasets (2M+ rows across
    7 months).
    """
    params = {"marketplace": marketplace}

    with conn.cursor() as cur:
        # ── Step 1: per-keyword aggregates into a temp table ──────────
        cur.execute("DROP TABLE IF EXISTS _compare_tmp")
        cur.execute(
            """
            CREATE TEMP TABLE _compare_tmp AS
            SELECT
                m.keyword_id,
                m.marketplace,
                MIN(m.data_month)   AS first_month,
                MAX(m.data_month)   AS last_month,
                COUNT(*)            AS month_count,
                JSONB_AGG(
                    JSONB_BUILD_OBJECT(
                        'data_month',    m.data_month,
                        'search_rank',   m.search_rank,
                        'search_volume', m.search_volume,
                        'ppc_bid_mid',   m.ppc_bid_mid,
                        'spr',           m.spr
                    )
                    ORDER BY m.data_month
                ) AS monthly
            FROM keyword_monthly_metrics m
            WHERE m.marketplace = %(marketplace)s
            GROUP BY m.keyword_id, m.marketplace
            """,
            params,
        )
        cur.execute("CREATE INDEX ON _compare_tmp (keyword_id, marketplace)")

        # ── Step 2: range metadata ──────────────────────────────────────
        cur.execute(
            """
            SELECT
                COUNT(DISTINCT data_month)::int AS total_months,
                MIN(data_month) AS range_start,
                MAX(data_month) AS range_end
            FROM keyword_monthly_metrics
            WHERE marketplace = %(marketplace)s
            """,
            params,
        )
        span = cur.fetchone()  # (total_months, range_start, range_end)
        total_months = span[0]
        range_start = span[1]
        range_end = span[2]

        # ── Step 3: INSERT base rows ────────────────────────────────────
        cur.execute(
            "DELETE FROM keyword_compare_snapshot WHERE marketplace = %(marketplace)s",
            params,
        )
        cur.execute(
            """
            INSERT INTO keyword_compare_snapshot (
                keyword_id, marketplace, keyword,
                first_month, last_month, month_count, total_months,
                monthly, trend_type, trend_type_cn
            )
            SELECT
                t.keyword_id, t.marketplace, k.keyword_normalized,
                t.first_month, t.last_month, t.month_count,
                %(total_months)s::int,
                t.monthly,
                'volatile', '波动观察'
            FROM _compare_tmp t
            JOIN keywords k ON k.id = t.keyword_id
            """,
            {**params, "total_months": total_months},
        )
        inserted = cur.rowcount
        print(f"  Inserted {inserted} keyword base rows.", flush=True)

        # ── Step 4: first-month values ──────────────────────────────────
        cur.execute(
            """
            UPDATE keyword_compare_snapshot s
            SET
                start_search_volume = fm.search_volume,
                start_rank          = fm.search_rank
            FROM keyword_monthly_metrics fm
            WHERE s.keyword_id   = fm.keyword_id
              AND s.marketplace  = fm.marketplace
              AND s.first_month  = fm.data_month
              AND s.marketplace  = %(marketplace)s
            """,
            params,
        )

        # ── Step 5: last-month values (most fields come from here) ──────
        cur.execute(
            """
            UPDATE keyword_compare_snapshot s
            SET
                end_search_volume      = lm.search_volume,
                end_rank               = lm.search_rank,
                ppc_bid_mid            = lm.ppc_bid_mid,
                spr                    = lm.spr,
                prev_month_rank        = lm.prev_month_rank,
                four_months_ago_rank   = lm.four_months_ago_rank,
                twelve_months_ago_rank = lm.twelve_months_ago_rank,
                keyword_translation    = lm.keyword_translation,
                category               = lm.category
            FROM keyword_monthly_metrics lm
            WHERE s.keyword_id   = lm.keyword_id
              AND s.marketplace  = lm.marketplace
              AND s.last_month   = lm.data_month
              AND s.marketplace  = %(marketplace)s
            """,
            params,
        )

        # ── Step 6: derived columns ─────────────────────────────────────
        cur.execute(
            """
            UPDATE keyword_compare_snapshot
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
                    ELSE ROUND(
                        ((end_search_volume - start_search_volume)
                         / start_search_volume::numeric) * 100, 2)
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

        # ── Step 6.5: statistical metrics from monthly JSONB ──────────────
        # Compute per-keyword stats across all available months:
        #   avg_search_volume, stddev, CV, linear regression slope & R², gap_count.
        # These feed into the 5-category classification in Step 7.
        cur.execute(
            """
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
            UPDATE keyword_compare_snapshot s
            SET
                avg_search_volume    = ms.avg_vol,
                stddev_search_volume = ms.stddev_vol,
                cv_search_volume     = CASE
                    WHEN ms.avg_vol > 0 THEN ms.stddev_vol / ms.avg_vol
                END,
                volume_slope         = ms.vol_slope,
                volume_r2            = ms.vol_r2,
                gap_count            = ms.total_months - ms.actual_count
            FROM stats ms
            WHERE s.keyword_id  = ms.keyword_id
              AND s.marketplace = ms.marketplace
              AND s.marketplace = %(marketplace)s
            """,
            params,
        )

        # ── Step 7: 5-category classification ──────────────────────────────
        # Priority order (first match wins):
        #   1. rising    — clear upward growth, linear fit
        #   2. falling   — clear downward decline, linear fit
        #   3. stable    — appears in most months, low volatility, no trend
        #   4. seasonal  — gappy pattern, irregular but not rare
        #   5. volatile  — everything else
        cur.execute(
            """
            UPDATE keyword_compare_snapshot
            SET
                trend_type = CASE
                    -- 上升型: ≥4 data points, positive slope, meaningful & linear
                    WHEN month_count >= 4
                         AND avg_search_volume > 0
                         AND volume_slope > 0
                         AND volume_slope / avg_search_volume > 0.05
                         AND volume_r2 >= 0.25
                        THEN 'rising'
                    -- 下降型: ≥4 data points, negative slope, meaningful & linear
                    WHEN month_count >= 4
                         AND avg_search_volume > 0
                         AND volume_slope < 0
                         AND ABS(volume_slope) / avg_search_volume > 0.05
                         AND volume_r2 >= 0.25
                        THEN 'falling'
                    -- 常年稳定型: ≥5 months, meaningful volume, low CV, no strong trend
                    WHEN month_count >= 5
                         AND avg_search_volume >= 100
                         AND cv_search_volume IS NOT NULL
                         AND cv_search_volume < 0.25
                         AND (volume_slope IS NULL
                              OR ABS(volume_slope) / NULLIF(avg_search_volume, 0) < 0.05)
                        THEN 'stable'
                    -- 季节型: has gaps (1~4 absent months), ≥3 appearances, irregular
                    WHEN gap_count BETWEEN 1 AND 4
                         AND month_count >= 3
                         AND avg_search_volume >= 100
                         AND (cv_search_volume >= 0.25
                              OR cv_search_volume IS NULL
                              OR volume_r2 < 0.25)
                        THEN 'seasonal'
                    -- 波动型: fallthrough
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
                         AND (volume_slope IS NULL
                              OR ABS(volume_slope) / NULLIF(avg_search_volume, 0) < 0.05)
                        THEN '常年稳定型'
                    WHEN gap_count BETWEEN 1 AND 4
                         AND month_count >= 3
                         AND avg_search_volume >= 100
                         AND (cv_search_volume >= 0.25
                              OR cv_search_volume IS NULL
                              OR volume_r2 < 0.25)
                        THEN '季节型'
                    ELSE '波动型'
                END
            WHERE marketplace = %(marketplace)s
            """,
            params,
        )

        # ── Clean up ────────────────────────────────────────────────────
        cur.execute("DROP TABLE IF EXISTS _compare_tmp")

    return inserted
