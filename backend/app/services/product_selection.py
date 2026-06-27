from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from datetime import date
from typing import Any

import psycopg

from app.utils import normalize_month

logger = logging.getLogger(__name__)


SORT_COLUMNS = {
    "search_volume": "search_volume",
    "product_selection_score": "product_selection_score",
    "search_rank": "search_rank",
    "months_seen_to_date": "months_seen_to_date",
    "ppc_bid_mid": "ppc_bid_mid",
    "spr": "spr",
}

CANDIDATE_LEVEL_SQL = """
            c.candidate_level_cn AS candidate_level_cn
"""



TREND_LABEL_SQL = """
            c.trend_label_cn AS trend_label_cn
"""



SELECTION_SEGMENT_SQL = """
            c.selection_segment_cn AS selection_segment_cn
"""


def _candidate_source(conn: psycopg.Connection, filters: CandidateFilters) -> str:
    """Return cache table when data is available, otherwise fall back to the live view.

    The cache table ``keyword_selection_candidates_monthly`` is refreshed by
    ``scripts/calculate_trends.py`` after every trend calculation run.  If the
    cache hasn't been populated yet for the requested month/marketplace we fall
    back to the real-time view ``v_mb_product_selection_candidates`` so operators
    never see an empty result set.
    """
    from app.services.product_selection_cache import cache_has_month

    month = filters.analysis_month or "(latest)"
    mp = filters.marketplace or "(any)"
    if cache_has_month(conn, filters.analysis_month, filters.marketplace):
        return "keyword_selection_candidates_monthly"

    logger.warning(
        "using live view v_mb_product_selection_candidates for %s / %s — "
        "consider running calculate_trends.py to refresh the cache table",
        month,
        mp,
    )
    return "v_mb_product_selection_candidates"


@dataclass(frozen=True)
class CandidateFilters:
    page: int = 1
    page_size: int = 100
    analysis_month: str | None = None
    marketplace: str | None = None
    keyword: str | None = None
    category: str | None = None
    trend_label: str | None = None
    candidate_level: str | None = None
    selection_segment: str | None = None
    is_candidate: bool | None = None
    favorite_only: bool = False
    search_volume_min: float | None = None
    search_volume_max: float | None = None
    score_min: float | None = None
    score_max: float | None = None
    ppc_min: float | None = None
    ppc_max: float | None = None
    spr_min: int | None = None
    spr_max: int | None = None
    sort_by: str = "product_selection_score"
    sort_order: str = "desc"


def _add_equal(where: list[str], params: list[Any], column: str, value: Any) -> None:
    if value is None or value == "":
        return
    where.append(f"{column} = %s")
    params.append(value)


def _add_min(where: list[str], params: list[Any], column: str, value: Any) -> None:
    if value is None:
        return
    where.append(f"{column} >= %s")
    params.append(value)


def _add_max(where: list[str], params: list[Any], column: str, value: Any) -> None:
    if value is None:
        return
    where.append(f"{column} <= %s")
    params.append(value)


def _candidate_where(filters: CandidateFilters) -> tuple[str, list[Any]]:
    where = ["1 = 1"]
    params: list[Any] = []

    if filters.analysis_month:
        where.append("analysis_month = %s::date")
        params.append(normalize_month(filters.analysis_month))
    else:
        where.append("analysis_month = (SELECT MAX(data_month) FROM keyword_monthly_metrics)")

    _add_equal(where, params, "marketplace", filters.marketplace)
    _add_equal(where, params, "category", filters.category)
    _add_equal(where, params, "trend_label", filters.trend_label)
    _add_equal(where, params, "selection_segment_cn", filters.selection_segment)

    if filters.candidate_level == "A级":
        where.append("product_selection_score >= 85")
    elif filters.candidate_level == "B级":
        where.append("product_selection_score >= 75")
        where.append("product_selection_score < 85")
    elif filters.candidate_level == "C级":
        where.append("product_selection_score >= 65")
        where.append("product_selection_score < 75")

    if filters.is_candidate is not None:
        where.append("is_product_selection_candidate = %s")
        params.append(filters.is_candidate)

    if filters.keyword:
        where.append("(keyword ILIKE %s OR keyword_translation ILIKE %s)")
        keyword_like = f"%{filters.keyword}%"
        params.extend([keyword_like, keyword_like])

    _add_min(where, params, "search_volume", filters.search_volume_min)
    _add_max(where, params, "search_volume", filters.search_volume_max)
    _add_min(where, params, "product_selection_score", filters.score_min)
    _add_max(where, params, "product_selection_score", filters.score_max)
    _add_min(where, params, "ppc_bid_mid", filters.ppc_min)
    _add_max(where, params, "ppc_bid_mid", filters.ppc_max)
    _add_min(where, params, "spr", filters.spr_min)
    _add_max(where, params, "spr", filters.spr_max)

    return " AND ".join(where), params


def list_candidates(conn: psycopg.Connection, filters: CandidateFilters) -> dict[str, Any]:
    return list_candidates_for_user(conn, filters, user_id=None)


def export_candidates_for_user(
    conn: psycopg.Connection,
    filters: CandidateFilters,
    user_id: int,
    max_rows: int = 5000,
) -> list[dict[str, Any]]:
    page_size = 500
    page = 1
    rows: list[dict[str, Any]] = []
    while len(rows) < max_rows:
        page_filters = replace(filters, page=page, page_size=page_size)
        result = list_candidates_for_user(conn, page_filters, user_id=user_id)
        items = result["items"]
        if not items:
            break
        rows.extend(items)
        if page >= result["pagination"]["total_pages"]:
            break
        page += 1
    return rows[:max_rows]


def list_candidates_for_user(
    conn: psycopg.Connection,
    filters: CandidateFilters,
    user_id: int | None,
) -> dict[str, Any]:
    page = max(filters.page, 1)
    page_size = min(max(filters.page_size, 1), 500)
    offset = (page - 1) * page_size
    sort_column = SORT_COLUMNS.get(filters.sort_by, "product_selection_score")
    sort_order = "ASC" if filters.sort_order.lower() == "asc" else "DESC"
    where_sql, params = _candidate_where(filters)
    source_table = _candidate_source(conn, filters)

    state_join = ""
    state_columns = """
            NULL::text AS user_status,
            NULL::text AS user_priority,
            FALSE AS user_is_favorite,
            NULL::text AS user_notes,
            NULL::timestamp AS user_updated_at,
    """
    state_params: list[Any] = []
    if user_id is not None:
        state_join = """
        LEFT JOIN keyword_selection_states s
          ON s.keyword_id = c.keyword_id
         AND s.analysis_month = c.analysis_month
         AND s.marketplace = c.marketplace
         AND s.owner_user_id = %s
        """
        state_columns = """
            s.status AS user_status,
            s.priority AS user_priority,
            COALESCE(s.is_favorite, FALSE) AS user_is_favorite,
            s.notes AS user_notes,
            s.updated_at AS user_updated_at,
        """
        state_params.append(user_id)

    favorite_sql = ""
    if filters.favorite_only and user_id is not None:
        favorite_sql = " AND COALESCE(s.is_favorite, FALSE) = TRUE"

    aliased_where_sql = (
        where_sql.replace("analysis_month", "c.analysis_month")
        .replace("marketplace", "c.marketplace")
        .replace("category", "c.category")
        .replace("trend_label", "c.trend_label")
        .replace("selection_segment_cn", "c.selection_segment_cn")
        .replace("is_product_selection_candidate", "c.is_product_selection_candidate")
        .replace("keyword ILIKE", "c.keyword ILIKE")
        .replace("keyword_translation ILIKE", "c.keyword_translation ILIKE")
        .replace("search_volume", "c.search_volume")
        .replace("product_selection_score", "c.product_selection_score")
        .replace("ppc_bid_mid", "c.ppc_bid_mid")
        .replace("spr", "c.spr")
    )

    select_sql = f"""
        SELECT
            c.keyword_id,
            c.keyword,
            c.keyword_translation,
            c.analysis_month,
            c.marketplace,
            c.category,
            c.search_rank,
            c.search_volume,
            c.months_seen_to_date,
            c.trend_label,
{TREND_LABEL_SQL},
{SELECTION_SEGMENT_SQL},
            c.demand_band_cn,
{CANDIDATE_LEVEL_SQL},
            c.product_selection_score,
            c.ppc_bid_mid,
            c.spr,
            c.click_share,
            c.conversion_share,
            c.is_product_selection_candidate,
            c.exclusion_reason_cn,
{state_columns}
            c.intent_score,
            c.demand_score,
            c.growth_score,
            c.stability_score,
            c.competition_access_score,
            c.conversion_signal_score
        FROM {source_table} c
        {state_join}
        WHERE {aliased_where_sql}
          {favorite_sql}
        ORDER BY {sort_column} {sort_order} NULLS LAST, search_volume DESC NULLS LAST
        LIMIT %s OFFSET %s
    """
    count_sql = f"""
        SELECT COUNT(*) AS total
        FROM {source_table} c
        {state_join if filters.favorite_only and user_id is not None else ""}
        WHERE {aliased_where_sql}
          {favorite_sql}
    """

    with conn.cursor() as cur:
        cur.execute(count_sql, [*(state_params if filters.favorite_only and user_id is not None else []), *params])
        total = cur.fetchone()["total"]
        cur.execute(select_sql, [*state_params, *params, page_size, offset])
        items = cur.fetchall()

    return {
        "items": items,
        "cached": source_table == "keyword_selection_candidates_monthly",
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": (total + page_size - 1) // page_size,
            "total_is_estimated": False,
            "has_more": page * page_size < total,
        },
    }


def _resolve_analysis_month(conn: psycopg.Connection, analysis_month: str | None) -> date:
    if analysis_month:
        return date.fromisoformat(normalize_month(analysis_month) or analysis_month)
    with conn.cursor() as cur:
        cur.execute("SELECT MAX(data_month) AS month FROM keyword_monthly_metrics")
        return cur.fetchone()["month"]


def upsert_candidate_state(
    conn: psycopg.Connection,
    *,
    keyword_id: int,
    user_id: int,
    analysis_month: str | None,
    marketplace: str,
    status: str | None = None,
    priority: str | None = None,
    is_favorite: bool | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    month = _resolve_analysis_month(conn, analysis_month)
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO keyword_selection_states (
                keyword_id,
                analysis_month,
                marketplace,
                owner_user_id,
                status,
                priority,
                is_favorite,
                notes
            )
            VALUES (
                %s,
                %s,
                %s,
                %s,
                COALESCE(%s, 'new'),
                %s,
                COALESCE(%s, FALSE),
                %s
            )
            ON CONFLICT (keyword_id, analysis_month, marketplace, owner_user_id)
            DO UPDATE SET
                status = COALESCE(EXCLUDED.status, keyword_selection_states.status),
                priority = COALESCE(EXCLUDED.priority, keyword_selection_states.priority),
                is_favorite = COALESCE(EXCLUDED.is_favorite, keyword_selection_states.is_favorite),
                notes = COALESCE(EXCLUDED.notes, keyword_selection_states.notes),
                updated_at = NOW()
            RETURNING *
            """,
            [keyword_id, month, marketplace, user_id, status, priority, is_favorite, notes],
        )
        state = cur.fetchone()
    conn.commit()
    return state


def add_candidate_note(
    conn: psycopg.Connection,
    *,
    keyword_id: int,
    user_id: int,
    analysis_month: str | None,
    marketplace: str,
    note: str,
) -> dict[str, Any]:
    month = _resolve_analysis_month(conn, analysis_month)
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO keyword_selection_notes (
                keyword_id,
                analysis_month,
                marketplace,
                user_id,
                note
            )
            VALUES (%s, %s, %s, %s, %s)
            RETURNING *
            """,
            [keyword_id, month, marketplace, user_id, note],
        )
        note_row = cur.fetchone()
    conn.commit()
    return note_row


def list_candidate_notes(
    conn: psycopg.Connection,
    *,
    keyword_id: int,
    analysis_month: str | None,
    marketplace: str | None,
) -> list[dict[str, Any]]:
    month = _resolve_analysis_month(conn, analysis_month)
    where = ["n.keyword_id = %s", "n.analysis_month = %s"]
    params: list[Any] = [keyword_id, month]
    if marketplace:
        where.append("n.marketplace = %s")
        params.append(marketplace)

    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT
                n.id,
                n.keyword_id,
                n.analysis_month,
                n.marketplace,
                n.note,
                n.created_at,
                u.id AS user_id,
                u.display_name,
                u.account
            FROM keyword_selection_notes n
            JOIN app_users u
              ON u.id = n.user_id
            WHERE {" AND ".join(where)}
            ORDER BY n.created_at DESC
            LIMIT 100
            """,
            params,
        )
        return cur.fetchall()


def get_candidate_detail(
    conn: psycopg.Connection,
    keyword_id: int,
    analysis_month: str | None = None,
    marketplace: str | None = None,
) -> dict[str, Any] | None:
    source_table = _candidate_source(
        conn,
        CandidateFilters(analysis_month=analysis_month, marketplace=marketplace),
    )
    where = ["keyword_id = %s"]
    params: list[Any] = [keyword_id]

    if analysis_month:
        where.append("analysis_month = %s::date")
        params.append(normalize_month(analysis_month))
    else:
        where.append("analysis_month = (SELECT MAX(data_month) FROM keyword_monthly_metrics)")

    _add_equal(where, params, "marketplace", marketplace)
    where_sql = " AND ".join(where)

    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT *
            FROM (
                SELECT
                    c.*,
{TREND_LABEL_SQL},
{SELECTION_SEGMENT_SQL},
{CANDIDATE_LEVEL_SQL}
                FROM {source_table} c
            ) c
            WHERE {where_sql}
            LIMIT 1
            """,
            params,
        )
        candidate = cur.fetchone()
        if not candidate:
            return None

        monthly_where = ["m.keyword_id = %s"]
        monthly_params: list[Any] = [keyword_id]
        if marketplace:
            monthly_where.append("m.marketplace = %s")
            monthly_params.append(marketplace)

        cur.execute(
            f"""
            SELECT
                m.data_month,
                m.marketplace,
                m.category,
                m.search_rank,
                m.search_volume,
                m.ppc_bid_mid,
                m.spr,
                m.click_share,
                m.conversion_share,
                o.trend_label,
                CASE o.trend_label
                    WHEN 'new' THEN '新出现词'
                    WHEN 'rising' THEN '搜索量上升 + 排名改善'
                    WHEN 'volume_up_rank_down' THEN '搜索量上升 + 排名下降'
                    WHEN 'rank_up_volume_down' THEN '排名改善 + 搜索量下降'
                    WHEN 'falling' THEN '搜索量下降 + 排名下降'
                    WHEN 'volume_up' THEN '仅搜索量上升'
                    WHEN 'volume_down' THEN '仅搜索量下降'
                    WHEN 'rank_up' THEN '仅排名改善'
                    WHEN 'rank_down' THEN '仅排名下降'
                    WHEN 'stable' THEN '稳定词'
                    WHEN 'volatile' THEN '波动观察'
                    WHEN 'seasonal_candidate' THEN '疑似季节词'
                    ELSE o.trend_label
                END AS trend_label_cn,
                o.opportunity_score,
                o.conversion_score
            FROM keyword_monthly_metrics m
            LEFT JOIN keyword_ops_monthly o
              ON o.keyword_id = m.keyword_id
             AND o.marketplace = m.marketplace
             AND o.analysis_month = m.data_month
            WHERE {" AND ".join(monthly_where)}
            ORDER BY m.data_month
            """,
            monthly_params,
        )
        monthly = cur.fetchall()

    return {"candidate": candidate, "monthly": monthly}


def list_months(conn: psycopg.Connection) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                data_month,
                marketplace,
                COUNT(*) AS keyword_count
            FROM keyword_monthly_metrics
            GROUP BY data_month, marketplace
            ORDER BY data_month DESC, marketplace
            """
        )
        return cur.fetchall()


def list_categories(
    conn: psycopg.Connection,
    analysis_month: str | None = None,
    marketplace: str | None = None,
) -> list[dict[str, Any]]:
    source_table = _candidate_source(
        conn,
        CandidateFilters(analysis_month=analysis_month, marketplace=marketplace),
    )
    where = ["1 = 1"]
    params: list[Any] = []
    if analysis_month:
        where.append("analysis_month = %s::date")
        params.append(normalize_month(analysis_month))
    else:
        where.append("analysis_month = (SELECT MAX(data_month) FROM keyword_monthly_metrics)")
    _add_equal(where, params, "marketplace", marketplace)

    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT
                category,
                COUNT(*) FILTER (WHERE is_product_selection_candidate) AS candidate_count,
                COUNT(*) FILTER (
                    WHERE is_product_selection_candidate AND product_selection_score >= 85
                ) AS level_a_count,
                COUNT(*) FILTER (
                    WHERE is_product_selection_candidate AND trend_label = 'rising' AND months_seen_total >= 2
                ) AS growth_candidate_count,
                COUNT(*) FILTER (
                    WHERE is_product_selection_candidate AND months_seen_total >= 4
                ) AS stable_candidate_count,
                ROUND(AVG(product_selection_score) FILTER (WHERE is_product_selection_candidate), 2) AS avg_candidate_score
            FROM {source_table}
            WHERE {" AND ".join(where)}
            GROUP BY category
            HAVING COUNT(*) FILTER (WHERE is_product_selection_candidate) > 0
            ORDER BY candidate_count DESC, level_a_count DESC
            LIMIT 300
            """,
            params,
        )
        return cur.fetchall()
