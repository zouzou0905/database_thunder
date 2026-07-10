from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from psycopg import Connection

from app.api.deps import get_current_user, require_admin
from app.core.cache import cached, invalidate
from app.db import get_connection
from app.services.exclusions import delete_exclusion, list_exclusions, update_exclusion, upsert_exclusion
from app.utils.json import to_jsonable


router = APIRouter(prefix="/exclusions", tags=["exclusions"])


class ExclusionCreateRequest(BaseModel):
    term: str = Field(min_length=1, max_length=200)
    match_type: str = Field(default="contains", pattern="^(contains|exact)$")
    exclusion_type: str = Field(default="brand", max_length=50)
    reason: str | None = None
    is_active: bool = True


class ExclusionUpdateRequest(BaseModel):
    reason: str | None = None
    is_active: bool | None = None


@router.get("")
@cached(ttl_seconds=300, namespace="exclusions", exclude=("conn", "current_user"))
def get_exclusions(
    active_only: bool = Query(default=False),
    current_user: dict = Depends(get_current_user),
    conn: Connection = Depends(get_connection),
) -> dict[str, object]:
    return {"items": to_jsonable(list_exclusions(conn, active_only=active_only))}


@router.post("")
def create_exclusion(
    payload: ExclusionCreateRequest,
    current_user: dict = Depends(require_admin),
    conn: Connection = Depends(get_connection),
) -> dict[str, object]:
    row = upsert_exclusion(
        conn,
        term=payload.term,
        match_type=payload.match_type,
        exclusion_type=payload.exclusion_type,
        reason=payload.reason,
        is_active=payload.is_active,
    )
    conn.commit()
    invalidate("exclusions")
    invalidate("meta")
    return {"exclusion": to_jsonable(row)}


@router.patch("/{exclusion_id}")
def patch_exclusion(
    exclusion_id: int,
    payload: ExclusionUpdateRequest,
    current_user: dict = Depends(require_admin),
    conn: Connection = Depends(get_connection),
) -> dict[str, object]:
    row = update_exclusion(
        conn,
        exclusion_id,
        reason=payload.reason,
        is_active=payload.is_active,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Exclusion not found")
    conn.commit()
    invalidate("exclusions")
    invalidate("meta")
    return {"exclusion": to_jsonable(row)}


@router.delete("/{exclusion_id}")
def remove_exclusion(
    exclusion_id: int,
    current_user: dict = Depends(require_admin),
    conn: Connection = Depends(get_connection),
) -> dict[str, object]:
    deleted = delete_exclusion(conn, exclusion_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Exclusion not found")
    invalidate("exclusions")
    invalidate("meta")
    return {"deleted": True}
