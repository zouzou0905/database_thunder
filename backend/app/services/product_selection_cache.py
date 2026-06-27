from __future__ import annotations

from typing import Any

import psycopg

from app.utils import normalize_month


CACHE_TABLE = "keyword_selection_candidates_monthly"
CACHE_COLUMNS = [
    "keyword_id",
    "keyword",
    "keyword_translation",
    "analysis_month",
    "marketplace",
    "category",
    "search_rank",
    "search_volume",
    "ppc_bid_low",
    "ppc_bid_mid",
    "ppc_bid_high",
    "spr",
    "click_share",
    "conversion_share",
    "rank_change_mom",
    "volume_change_mom",
    "volume_growth_rate_mom",
    "trend_label",
    "trend_label_cn",
    "opportunity_score",
    "competition_score",
    "conversion_score",
    "prev_1m_rank",
    "prev_2m_rank",
    "prev_3m_rank",
    "prev_1m_search_volume",
    "prev_2m_search_volume",
    "prev_3m_search_volume",
    "rank_change_1m",
    "rank_change_3m",
    "search_volume_growth_1m_pct",
    "search_volume_growth_3m_pct",
    "months_seen_to_date",
    "months_seen_total",
    "first_seen_month",
    "last_seen_month",
    "word_count",
    "is_media_category",
    "is_unknown_category",
    "is_manual_excluded",
    "intent_score",
    "demand_score",
    "growth_score",
    "stability_score",
    "competition_access_score",
    "conversion_signal_score",
    "selection_segment_cn",
    "demand_band_cn",
    "exclusion_reason_cn",
    "is_product_selection_candidate",
    "product_selection_score",
    "candidate_level_cn",
]


def _base_filters(
    analysis_month: str | None = None,
    marketplace: str | None = None,
) -> tuple[list[str], list[Any]]:
    where: list[str] = []
    params: list[Any] = []
    if analysis_month:
        where.append("analysis_month = %s::date")
        params.append(normalize_month(analysis_month))
    if marketplace:
        where.append("marketplace = %s")
        params.append(marketplace)
    return where, params


def _term_filter(term: str, match_type: str) -> tuple[str, list[Any]]:
    if match_type == "exact":
        return "LOWER(keyword) = LOWER(%s)", [term]
    return "LOWER(keyword) LIKE '%' || LOWER(%s) || '%'", [term]


def cache_has_month(conn: psycopg.Connection, analysis_month: str | None, marketplace: str | None) -> bool:
    where, params = _base_filters(analysis_month, marketplace)
    if not where:
        where.append("analysis_month = (SELECT MAX(data_month) FROM keyword_monthly_metrics)")
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT EXISTS (
                SELECT 1
                FROM {CACHE_TABLE}
                WHERE {" AND ".join(where)}
                LIMIT 1
            ) AS has_cache
            """,
            params,
        )
        return bool(cur.fetchone()["has_cache"])


def refresh_cache(
    conn: psycopg.Connection,
    *,
    analysis_month: str | None = None,
    marketplace: str | None = None,
) -> int:
    where, params = _base_filters(analysis_month, marketplace)
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    column_sql = ", ".join(CACHE_COLUMNS)
    excluded_sql = ",\n                ".join(
        f"{column} = EXCLUDED.{column}" for column in CACHE_COLUMNS if column not in {"keyword_id", "analysis_month", "marketplace"}
    )
    with conn.cursor() as cur:
        cur.execute(
            f"""
            DELETE FROM {CACHE_TABLE}
            {where_sql}
            """,
            params,
        )
        cur.execute(
            f"""
            INSERT INTO {CACHE_TABLE} (
                {column_sql},
                refreshed_at
            )
            SELECT
                {column_sql},
                NOW() AS refreshed_at
            FROM v_mb_product_selection_candidates
            {where_sql}
            ON CONFLICT (keyword_id, analysis_month, marketplace)
            DO UPDATE SET
                {excluded_sql},
                refreshed_at = NOW()
            """,
            params,
        )
        return cur.rowcount


def refresh_cache_for_term(
    conn: psycopg.Connection,
    *,
    term: str,
    match_type: str,
    marketplace: str | None = None,
) -> int:
    term_sql, term_params = _term_filter(term, match_type)
    where = [term_sql]
    params = [*term_params]
    if marketplace:
        where.append("marketplace = %s")
        params.append(marketplace)
    where_sql = "WHERE " + " AND ".join(where)
    column_sql = ", ".join(CACHE_COLUMNS)
    excluded_sql = ",\n                ".join(
        f"{column} = EXCLUDED.{column}" for column in CACHE_COLUMNS if column not in {"keyword_id", "analysis_month", "marketplace"}
    )
    with conn.cursor() as cur:
        cur.execute(
            f"""
            DELETE FROM {CACHE_TABLE}
            {where_sql}
            """,
            params,
        )
        cur.execute(
            f"""
            INSERT INTO {CACHE_TABLE} (
                {column_sql},
                refreshed_at
            )
            SELECT
                {column_sql},
                NOW() AS refreshed_at
            FROM v_mb_product_selection_candidates
            {where_sql}
            ON CONFLICT (keyword_id, analysis_month, marketplace)
            DO UPDATE SET
                {excluded_sql},
                refreshed_at = NOW()
            """,
            params,
        )
        return cur.rowcount
