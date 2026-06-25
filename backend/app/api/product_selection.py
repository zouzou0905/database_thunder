from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from psycopg import Connection

from app.api.deps import get_current_user
from app.db import get_connection
from app.services.product_selection import (
    CandidateFilters,
    add_candidate_note,
    get_candidate_detail,
    list_candidate_notes,
    list_candidates_for_user,
    upsert_candidate_state,
)
from app.utils.json import to_jsonable


router = APIRouter(prefix="/product-selection", tags=["product-selection"])


class StateUpdateRequest(BaseModel):
    analysis_month: str | None = None
    marketplace: str = "UK"
    status: str | None = Field(default=None, pattern="^(new|watching|researching|rejected|approved|launched)$")
    priority: str | None = Field(default=None, pattern="^(low|medium|high)$")
    is_favorite: bool | None = None
    notes: str | None = None


class NoteCreateRequest(BaseModel):
    analysis_month: str | None = None
    marketplace: str = "UK"
    note: str = Field(min_length=1, max_length=5000)


@router.get("/candidates")
def candidates(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=500),
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
    current_user: dict = Depends(get_current_user),
    conn: Connection = Depends(get_connection),
) -> dict[str, object]:
    filters = CandidateFilters(
        page=page,
        page_size=page_size,
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
    return to_jsonable(list_candidates_for_user(conn, filters, user_id=current_user["id"]))


@router.get("/candidates/{keyword_id}")
def candidate_detail(
    keyword_id: int,
    analysis_month: str | None = Query(default=None),
    marketplace: str | None = Query(default=None),
    current_user: dict = Depends(get_current_user),
    conn: Connection = Depends(get_connection),
) -> dict[str, object]:
    detail = get_candidate_detail(
        conn,
        keyword_id=keyword_id,
        analysis_month=analysis_month,
        marketplace=marketplace,
    )
    if not detail:
        raise HTTPException(status_code=404, detail="Candidate keyword not found")
    detail["notes"] = list_candidate_notes(
        conn,
        keyword_id=keyword_id,
        analysis_month=analysis_month,
        marketplace=marketplace,
    )
    return to_jsonable(detail)


@router.patch("/candidates/{keyword_id}/state")
def update_candidate_state(
    keyword_id: int,
    payload: StateUpdateRequest,
    current_user: dict = Depends(get_current_user),
    conn: Connection = Depends(get_connection),
) -> dict[str, object]:
    state = upsert_candidate_state(
        conn,
        keyword_id=keyword_id,
        user_id=current_user["id"],
        analysis_month=payload.analysis_month,
        marketplace=payload.marketplace,
        status=payload.status,
        priority=payload.priority,
        is_favorite=payload.is_favorite,
        notes=payload.notes,
    )
    return {"state": to_jsonable(state)}


@router.post("/candidates/{keyword_id}/notes")
def create_candidate_note(
    keyword_id: int,
    payload: NoteCreateRequest,
    current_user: dict = Depends(get_current_user),
    conn: Connection = Depends(get_connection),
) -> dict[str, object]:
    note = add_candidate_note(
        conn,
        keyword_id=keyword_id,
        user_id=current_user["id"],
        analysis_month=payload.analysis_month,
        marketplace=payload.marketplace,
        note=payload.note,
    )
    upsert_candidate_state(
        conn,
        keyword_id=keyword_id,
        user_id=current_user["id"],
        analysis_month=payload.analysis_month,
        marketplace=payload.marketplace,
        notes=payload.note,
    )
    return {"note": to_jsonable(note)}
