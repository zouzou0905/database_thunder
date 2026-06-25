"""Pre-computed snapshot for the keyword horizontal compare module.

The compare query aggregates keyword_monthly_metrics across multiple months
with window functions, JSONB_AGG, and correlated EXISTS subqueries — far too
heavy for real-time API use.  This module mirrors the product-selection cache
pattern: a materialized table refreshed after each trend calculation run.
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

        # ── Step 7: trend_type for keywords that existed before range ───
        range_params = {**params, "range_start": range_start, "range_end": range_end}
        cur.execute(
            """
            UPDATE keyword_compare_snapshot s
            SET
                trend_type = CASE
                    WHEN s.first_month = %(range_end)s::date
                         AND hb.keyword_id IS NULL THEN 'new'
                    WHEN s.first_month > %(range_start)s::date
                         AND hb.keyword_id IS NOT NULL THEN 'reappeared'
                    WHEN s.month_count = s.total_months
                         AND s.start_search_volume > 0
                         AND ((s.end_search_volume - s.start_search_volume)
                              / s.start_search_volume::numeric) >= 0.20
                        THEN 'continuous_rising'
                    WHEN s.start_search_volume > 0
                         AND ((s.end_search_volume - s.start_search_volume)
                              / s.start_search_volume::numeric) >= 0.20
                        THEN 'rising'
                    WHEN s.month_count = s.total_months
                         AND s.start_search_volume > 0
                         AND ((s.end_search_volume - s.start_search_volume)
                              / s.start_search_volume::numeric) <= -0.20
                        THEN 'continuous_falling'
                    WHEN s.start_search_volume > 0
                         AND ((s.end_search_volume - s.start_search_volume)
                              / s.start_search_volume::numeric) <= -0.20
                        THEN 'falling'
                    WHEN s.month_count >= 3
                         AND s.start_search_volume > 0
                         AND ABS((s.end_search_volume - s.start_search_volume)
                                 / s.start_search_volume::numeric) < 0.10
                        THEN 'stable'
                    WHEN s.month_count = s.total_months THEN 'continuous'
                    ELSE 'volatile'
                END,
                trend_type_cn = CASE
                    WHEN s.first_month = %(range_end)s::date
                         AND hb.keyword_id IS NULL THEN '区间新出现'
                    WHEN s.first_month > %(range_start)s::date
                         AND hb.keyword_id IS NOT NULL THEN '区间回归'
                    WHEN s.month_count = s.total_months
                         AND s.start_search_volume > 0
                         AND ((s.end_search_volume - s.start_search_volume)
                              / s.start_search_volume::numeric) >= 0.20
                        THEN '连续上升'
                    WHEN s.start_search_volume > 0
                         AND ((s.end_search_volume - s.start_search_volume)
                              / s.start_search_volume::numeric) >= 0.20
                        THEN '明显上升'
                    WHEN s.month_count = s.total_months
                         AND s.start_search_volume > 0
                         AND ((s.end_search_volume - s.start_search_volume)
                              / s.start_search_volume::numeric) <= -0.20
                        THEN '连续下降'
                    WHEN s.start_search_volume > 0
                         AND ((s.end_search_volume - s.start_search_volume)
                              / s.start_search_volume::numeric) <= -0.20
                        THEN '明显下降'
                    WHEN s.month_count >= 3
                         AND s.start_search_volume > 0
                         AND ABS((s.end_search_volume - s.start_search_volume)
                                 / s.start_search_volume::numeric) < 0.10
                        THEN '相对稳定'
                    WHEN s.month_count = s.total_months THEN '连续出现'
                    ELSE '波动观察'
                END
            FROM (
                SELECT DISTINCT keyword_id
                FROM keyword_monthly_metrics
                WHERE marketplace = %(marketplace)s
                  AND data_month < %(range_start)s::date
            ) hb
            WHERE s.keyword_id = hb.keyword_id
              AND s.marketplace = %(marketplace)s
            """,
            range_params,
        )

        # ── Step 8: trend_type for keywords NOT existing before range ───
        cur.execute(
            """
            UPDATE keyword_compare_snapshot s
            SET
                trend_type = CASE
                    WHEN s.first_month = %(range_end)s::date THEN 'new'
                    WHEN s.month_count = s.total_months
                         AND s.start_search_volume > 0
                         AND ((s.end_search_volume - s.start_search_volume)
                              / s.start_search_volume::numeric) >= 0.20
                        THEN 'continuous_rising'
                    WHEN s.start_search_volume > 0
                         AND ((s.end_search_volume - s.start_search_volume)
                              / s.start_search_volume::numeric) >= 0.20
                        THEN 'rising'
                    WHEN s.month_count = s.total_months
                         AND s.start_search_volume > 0
                         AND ((s.end_search_volume - s.start_search_volume)
                              / s.start_search_volume::numeric) <= -0.20
                        THEN 'continuous_falling'
                    WHEN s.start_search_volume > 0
                         AND ((s.end_search_volume - s.start_search_volume)
                              / s.start_search_volume::numeric) <= -0.20
                        THEN 'falling'
                    WHEN s.month_count >= 3
                         AND s.start_search_volume > 0
                         AND ABS((s.end_search_volume - s.start_search_volume)
                                 / s.start_search_volume::numeric) < 0.10
                        THEN 'stable'
                    WHEN s.month_count = s.total_months THEN 'continuous'
                    ELSE 'volatile'
                END,
                trend_type_cn = CASE
                    WHEN s.first_month = %(range_end)s::date THEN '区间新出现'
                    WHEN s.month_count = s.total_months
                         AND s.start_search_volume > 0
                         AND ((s.end_search_volume - s.start_search_volume)
                              / s.start_search_volume::numeric) >= 0.20
                        THEN '连续上升'
                    WHEN s.start_search_volume > 0
                         AND ((s.end_search_volume - s.start_search_volume)
                              / s.start_search_volume::numeric) >= 0.20
                        THEN '明显上升'
                    WHEN s.month_count = s.total_months
                         AND s.start_search_volume > 0
                         AND ((s.end_search_volume - s.start_search_volume)
                              / s.start_search_volume::numeric) <= -0.20
                        THEN '连续下降'
                    WHEN s.start_search_volume > 0
                         AND ((s.end_search_volume - s.start_search_volume)
                              / s.start_search_volume::numeric) <= -0.20
                        THEN '明显下降'
                    WHEN s.month_count >= 3
                         AND s.start_search_volume > 0
                         AND ABS((s.end_search_volume - s.start_search_volume)
                                 / s.start_search_volume::numeric) < 0.10
                        THEN '相对稳定'
                    WHEN s.month_count = s.total_months THEN '连续出现'
                    ELSE '波动观察'
                END
            WHERE s.marketplace = %(marketplace)s
              AND s.keyword_id NOT IN (
                  SELECT DISTINCT keyword_id
                  FROM keyword_monthly_metrics
                  WHERE marketplace = %(marketplace)s
                    AND data_month < %(range_start)s::date
              )
            """,
            range_params,
        )

        # ── Clean up ────────────────────────────────────────────────────
        cur.execute("DROP TABLE IF EXISTS _compare_tmp")

    return inserted
