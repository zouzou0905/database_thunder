from __future__ import annotations

from io import BytesIO

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from psycopg import Connection

from app.api.deps import get_current_user
from app.db import get_connection
from app.services.product_selection import CandidateFilters, export_candidates_for_user


router = APIRouter(prefix="/exports", tags=["exports"])


EXPORT_COLUMNS = [
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


@router.get("/product-selection")
def export_product_selection(
    analysis_month: str | None = Query(default=None),
    marketplace: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    category: str | None = Query(default=None),
    trend_label: str | None = Query(default=None),
    candidate_level: str | None = Query(default=None),
    selection_segment: str | None = Query(default=None),
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
    max_rows: int = Query(default=5000, ge=1, le=20000),
    current_user: dict = Depends(get_current_user),
    conn: Connection = Depends(get_connection),
) -> StreamingResponse:
    filters = CandidateFilters(
        analysis_month=analysis_month,
        marketplace=marketplace,
        keyword=keyword,
        category=category,
        trend_label=trend_label,
        candidate_level=candidate_level,
        selection_segment=selection_segment,
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
    )
    rows = export_candidates_for_user(conn, filters, user_id=current_user["id"], max_rows=max_rows)

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "选品候选词"
    sheet.append([title for title, _ in EXPORT_COLUMNS])
    for row in rows:
        sheet.append([row.get(field) for _, field in EXPORT_COLUMNS])

    for column_cells in sheet.columns:
        max_length = max(len(str(cell.value or "")) for cell in column_cells)
        sheet.column_dimensions[column_cells[0].column_letter].width = min(max(max_length + 2, 10), 42)

    output = BytesIO()
    workbook.save(output)
    output.seek(0)

    filename = "product_selection_candidates.xlsx"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers,
    )
