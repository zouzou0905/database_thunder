from __future__ import annotations

import csv
from io import BytesIO, StringIO
from urllib.parse import quote

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from psycopg import Connection

from app.api.deps import get_current_user
from app.db import get_connection
from app.services.product_selection import CandidateFilters, export_candidates_for_user
from app.services.keyword_compare import (
    KeywordCompareFilters,
    count_keyword_comparisons,
    export_comparisons,
    resolve_keyword_compare_range,
)


router = APIRouter(prefix="/exports", tags=["exports"])


CANDIDATE_COLUMNS = [
    ("关键词", "keyword"),
    ("中文释义", "keyword_translation"),
    ("月份", "analysis_month"),
    ("站点", "marketplace"),
    ("类目", "category"),
    ("搜索排名", "search_rank"),
    ("搜索量", "search_volume"),
    ("已出现月数", "months_seen_to_date"),
    ("趋势", "trend_label_cn"),
    ("选品类型", "selection_segment_cn"),
    ("需求层级", "demand_band_cn"),
    ("候选等级", "candidate_level_cn"),
    ("选品分", "product_selection_score"),
    ("PPC中位价", "ppc_bid_mid"),
    ("SPR", "spr"),
    ("点击份额", "click_share"),
    ("转化份额", "conversion_share"),
    ("我的状态", "user_status"),
    ("我的优先级", "user_priority"),
    ("是否收藏", "user_is_favorite"),
    ("我的备注", "user_notes"),
]

COMPARE_COLUMNS = [
    ("关键词", "keyword"),
    ("中文释义", "keyword_translation"),
    ("类目", "category"),
    ("站点", "marketplace"),
    ("起始月份", "first_month"),
    ("结束月份", "last_month"),
    ("起始搜索量", "start_search_volume"),
    ("结束搜索量", "end_search_volume"),
    ("搜索量变化", "search_volume_change"),
    ("增长率(%)", "search_volume_growth_rate"),
    ("起始排名", "start_rank"),
    ("结束排名", "end_rank"),
    ("排名变化", "rank_change"),
    ("出现月数", "month_count"),
    ("总月数", "total_months"),
    ("趋势类型", "trend_type_cn"),
    ("PPC中位价", "ppc_bid_mid"),
    ("SPR", "spr"),
    ("上月排名", "prev_month_rank"),
    ("4月前排名", "four_months_ago_rank"),
    ("12月前排名", "twelve_months_ago_rank"),
    ("我的状态", "user_status"),
    ("是否收藏", "user_is_favorite"),
    ("我的备注", "user_notes"),
    ("节日标签", "holiday_label"),
    ("节日置信度", "holiday_confidence"),
    ("命中节日词", "holiday_matched_terms"),
    ("节日趋势窗口", "holiday_trend_window"),
    ("节日窗口增长率(%)", "holiday_window_growth"),
]


def _build_xlsx(columns: list[tuple[str, str]], rows: list[dict]) -> BytesIO:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "导出数据"
    sheet.append([title for title, _ in columns])
    for row in rows:
        sheet.append([row.get(field) for _, field in columns])
    for column_cells in sheet.columns:
        max_length = max(len(str(cell.value or "")) for cell in column_cells)
        sheet.column_dimensions[column_cells[0].column_letter].width = min(max(max_length + 2, 10), 42)
    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    return output


def _build_csv(columns: list[tuple[str, str]], rows: list[dict]) -> StringIO:
    output = StringIO()
    output.write("\ufeff")
    writer = csv.writer(output)
    writer.writerow([title for title, _ in columns])
    for row in rows:
        writer.writerow([row.get(field, "") for _, field in columns])
    output.seek(0)
    return output


def _alias_candidate_where(where_sql: str) -> str:
    return (
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


def _count_candidates(conn: Connection, filters: CandidateFilters, user_id: int) -> int:
    from app.services.product_selection import _candidate_where, _candidate_source
    where_sql, params = _candidate_where(filters)
    source_table = _candidate_source(conn, filters)
    aliased_where_sql = _alias_candidate_where(where_sql)
    if filters.favorite_only and user_id is not None:
        count_sql = f"""
            SELECT COUNT(*)
            FROM {source_table} c
            JOIN keyword_selection_states s
              ON s.keyword_id = c.keyword_id
             AND s.analysis_month = c.analysis_month
             AND s.marketplace = c.marketplace
             AND s.owner_user_id = %s
             AND s.is_favorite = TRUE
            WHERE {aliased_where_sql}
        """
        query_params = [user_id, *params]
    else:
        count_sql = f"SELECT COUNT(*) FROM {source_table} c WHERE {aliased_where_sql}"
        query_params = params
    with conn.cursor() as cur:
        cur.execute(count_sql, query_params)
        row = cur.fetchone()
        return row["count"] if isinstance(row, dict) else row[0]


def _count_compare(conn: Connection, filters: KeywordCompareFilters) -> int:
    return count_keyword_comparisons(conn, filters)


@router.get("/count")
def export_preview_count(
    source: str = Query(default="candidates", pattern="^(candidates|compare)$"),
    analysis_month: str | None = Query(default=None),
    marketplace: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    category: str | None = Query(default=None),
    trend_label: str | None = Query(default=None),
    candidate_level: str | None = Query(default=None),
    is_candidate: bool | None = Query(default=None),
    favorite_only: bool = Query(default=False),
    search_volume_min: float | None = Query(default=None),
    search_volume_max: float | None = Query(default=None),
    score_min: float | None = Query(default=None),
    score_max: float | None = Query(default=None),
    ppc_min: float | None = Query(default=None),
    ppc_max: float | None = Query(default=None),
    spr_min: int | None = Query(default=None),
    spr_max: int | None = Query(default=None),
    # compare-only filters
    start_month: str | None = Query(default=None),
    end_month: str | None = Query(default=None),
    trend_type: str | None = Query(default=None),
    growth_rate_min: float | None = Query(default=None),
    growth_rate_max: float | None = Query(default=None),
    month_count_min: int | None = Query(default=None),
    month_count_max: int | None = Query(default=None),
    sort_by: str = Query(default="product_selection_score"),
    current_user: dict = Depends(get_current_user),
    conn: Connection = Depends(get_connection),
) -> dict:
    """Return accurate row count for the given filters using COUNT(*)."""
    if source == "compare":
        filters = KeywordCompareFilters(
            start_month=start_month, end_month=end_month,
            marketplace=marketplace, keyword=keyword, category=category,
            trend_type=trend_type or "",
            search_volume_min=search_volume_min,
            search_volume_max=search_volume_max,
            growth_rate_min=growth_rate_min,
            growth_rate_max=growth_rate_max,
            month_count_min=month_count_min,
            month_count_max=month_count_max,
            ppc_min=ppc_min, ppc_max=ppc_max,
            spr_min=spr_min, spr_max=spr_max,
            sort_by=sort_by,
        )
        count = _count_compare(conn, filters)
    else:
        filters = CandidateFilters(
            analysis_month=analysis_month, marketplace=marketplace,
            keyword=keyword, category=category, trend_label=trend_label or "",
            candidate_level=candidate_level or "",
            is_candidate=is_candidate, favorite_only=favorite_only,
            search_volume_min=search_volume_min,
            search_volume_max=search_volume_max,
            score_min=score_min, score_max=score_max,
            ppc_min=ppc_min, ppc_max=ppc_max,
            spr_min=spr_min, spr_max=spr_max,
            sort_by=sort_by,
        )
        count = _count_candidates(conn, filters, user_id=current_user["id"])
    return {"count": count, "total_is_estimated": False, "total_label": "exact"}


def _enrich_compare_rows_with_holiday_tags(
    conn: Connection, rows: list[dict], marketplace: str | None,
    range_start: str | None = None, range_end: str | None = None,
) -> None:
    if not rows or not marketplace:
        return
    keyword_ids = list({r["keyword_id"] for r in rows if r.get("keyword_id")})
    if not keyword_ids:
        for r in rows:
            r["holiday_label"] = r["holiday_confidence"] = r["holiday_matched_terms"] = r["holiday_trend_window"] = r["holiday_window_growth"] = ""
        return
    if range_start and range_end:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT keyword_id, holiday_name_cn, confidence, matched_terms,
                       trend_start_month, trend_end_month, growth_rate
                FROM keyword_holiday_tags
                WHERE keyword_id = ANY(%s) AND marketplace = %s
                  AND make_date(trend_year, trend_start_month, 1) >= %s::date
                  AND make_date(trend_year, trend_end_month, 1) <= %s::date
                ORDER BY keyword_id, confidence DESC, holiday_name_cn
                """,
                [keyword_ids, marketplace, range_start, range_end],
            )
            tags_rows = cur.fetchall()
    else:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT keyword_id, holiday_name_cn, confidence, matched_terms,
                       trend_start_month, trend_end_month, growth_rate
                FROM keyword_holiday_tags
                WHERE keyword_id = ANY(%s) AND marketplace = %s
                ORDER BY keyword_id, confidence DESC, holiday_name_cn
                """,
                [keyword_ids, marketplace],
            )
            tags_rows = cur.fetchall()
    tags_by_kid: dict[int, list[dict]] = {}
    for t in tags_rows:
        tags_by_kid.setdefault(t["keyword_id"], []).append(t)
    for r in rows:
        tags = tags_by_kid.get(r["keyword_id"], [])
        if not tags:
            r["holiday_label"] = r["holiday_confidence"] = r["holiday_matched_terms"] = r["holiday_trend_window"] = r["holiday_window_growth"] = ""
        else:
            r["holiday_label"] = " / ".join(t["holiday_name_cn"] for t in tags)
            r["holiday_confidence"] = " / ".join(t["confidence"] for t in tags)
            r["holiday_matched_terms"] = " / ".join(", ".join(t["matched_terms"]) if isinstance(t["matched_terms"], list) else str(t["matched_terms"]) for t in tags)
            r["holiday_trend_window"] = " / ".join(f"{t['trend_start_month']}-{t['trend_end_month']}月" for t in tags)
            r["holiday_window_growth"] = " / ".join(f"{t['growth_rate'] * 100:.1f}%" if t["growth_rate"] is not None else "-" for t in tags)


@router.get("/download")
def export_download(
    source: str = Query(default="candidates", pattern="^(candidates|compare)$"),
    format: str = Query(default="xlsx", pattern="^(xlsx|csv)$"),
    filename: str = Query(default="export"),
    max_rows: int = Query(default=5000, ge=1, le=20000),
    # candidate filters
    analysis_month: str | None = Query(default=None),
    marketplace: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    category: str | None = Query(default=None),
    trend_label: str | None = Query(default=None),
    candidate_level: str | None = Query(default=None),
    is_candidate: bool | None = Query(default=None),
    favorite_only: bool = Query(default=False),
    search_volume_min: float | None = Query(default=None),
    search_volume_max: float | None = Query(default=None),
    score_min: float | None = Query(default=None),
    score_max: float | None = Query(default=None),
    ppc_min: float | None = Query(default=None),
    ppc_max: float | None = Query(default=None),
    spr_min: int | None = Query(default=None),
    spr_max: int | None = Query(default=None),
    # compare-only filters
    start_month: str | None = Query(default=None),
    end_month: str | None = Query(default=None),
    trend_type: str | None = Query(default=None),
    growth_rate_min: float | None = Query(default=None),
    growth_rate_max: float | None = Query(default=None),
    month_count_min: int | None = Query(default=None),
    month_count_max: int | None = Query(default=None),
    sort_by: str = Query(default="product_selection_score"),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$"),
    current_user: dict = Depends(get_current_user),
    conn: Connection = Depends(get_connection),
) -> StreamingResponse:
    if source == "compare":
        columns = COMPARE_COLUMNS
        filters = KeywordCompareFilters(
            start_month=start_month, end_month=end_month,
            marketplace=marketplace, keyword=keyword, category=category,
            trend_type=trend_type or "",
            search_volume_min=search_volume_min,
            search_volume_max=search_volume_max,
            growth_rate_min=growth_rate_min,
            growth_rate_max=growth_rate_max,
            month_count_min=month_count_min,
            month_count_max=month_count_max,
            ppc_min=ppc_min, ppc_max=ppc_max,
            spr_min=spr_min, spr_max=spr_max,
            sort_by=sort_by, sort_order=sort_order,
        )
        rows = export_comparisons(conn, filters, user_id=current_user["id"], max_rows=max_rows)
        resolved_start, resolved_end = resolve_keyword_compare_range(conn, filters)
        _enrich_compare_rows_with_holiday_tags(
            conn, rows, marketplace,
            range_start=resolved_start.isoformat(),
            range_end=resolved_end.isoformat(),
        )
    else:
        columns = CANDIDATE_COLUMNS
        filters = CandidateFilters(
            analysis_month=analysis_month, marketplace=marketplace,
            keyword=keyword, category=category, trend_label=trend_label or "",
            candidate_level=candidate_level or "",
            is_candidate=is_candidate, favorite_only=favorite_only,
            search_volume_min=search_volume_min,
            search_volume_max=search_volume_max,
            score_min=score_min, score_max=score_max,
            ppc_min=ppc_min, ppc_max=ppc_max,
            spr_min=spr_min, spr_max=spr_max,
            sort_by=sort_by, sort_order=sort_order,
        )
        rows = export_candidates_for_user(conn, filters, user_id=current_user["id"], max_rows=max_rows)

    safe_filename = filename.replace("/", "_").replace("\\", "_")
    if format == "csv":
        output = _build_csv(columns, rows)
        ext = "csv"
        media_type = "text/csv; charset=utf-8-sig"
    else:
        output = _build_xlsx(columns, rows)
        ext = "xlsx"
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    download_name = f"{safe_filename}.{ext}"
    headers = {
        "Content-Disposition": (
            f'attachment; filename="{quote(download_name, safe="")}"'
            f"; filename*=UTF-8''{quote(download_name)}"
        )
    }
    return StreamingResponse(
        output,
        media_type=media_type,
        headers=headers,
    )


@router.get("/product-selection")
def export_product_selection_legacy(
    max_rows: int = Query(default=5000, ge=1, le=20000),
    analysis_month: str | None = Query(default=None),
    marketplace: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    category: str | None = Query(default=None),
    trend_label: str | None = Query(default=None),
    candidate_level: str | None = Query(default=None),
    is_candidate: bool | None = Query(default=None),
    favorite_only: bool = Query(default=False),
    search_volume_min: float | None = Query(default=None),
    search_volume_max: float | None = Query(default=None),
    score_min: float | None = Query(default=None),
    score_max: float | None = Query(default=None),
    ppc_min: float | None = Query(default=None),
    ppc_max: float | None = Query(default=None),
    spr_min: int | None = Query(default=None),
    spr_max: int | None = Query(default=None),
    sort_by: str = Query(default="product_selection_score"),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$"),
    current_user: dict = Depends(get_current_user),
    conn: Connection = Depends(get_connection),
) -> StreamingResponse:
    return export_download(
        source="candidates",
        format="xlsx",
        filename="选品候选词",
        max_rows=max_rows,
        analysis_month=analysis_month,
        marketplace=marketplace,
        keyword=keyword,
        category=category,
        trend_label=trend_label,
        candidate_level=candidate_level,
        is_candidate=is_candidate,
        favorite_only=favorite_only,
        search_volume_min=search_volume_min,
        search_volume_max=search_volume_max,
        score_min=score_min,
        score_max=score_max,
        ppc_min=ppc_min,
        ppc_max=ppc_max,
        spr_min=spr_min,
        spr_max=spr_max,
        sort_by=sort_by,
        sort_order=sort_order,
        current_user=current_user,
        conn=conn,
    )
