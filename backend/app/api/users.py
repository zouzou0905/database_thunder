from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from psycopg import Connection, errors

from app.api.deps import require_admin
from app.db import get_connection
from app.services.users import create_user, list_users, update_user
from app.utils.json import to_jsonable


router = APIRouter(prefix="/users", tags=["users"])


class UserCreateRequest(BaseModel):
    account: str = Field(min_length=2, max_length=50)
    display_name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=6, max_length=200)
    role: str = Field(default="operator", pattern="^(admin|manager|operator|viewer)$")
    is_active: bool = True


class UserUpdateRequest(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=100)
    password: str | None = Field(default=None, min_length=6, max_length=200)
    role: str | None = Field(default=None, pattern="^(admin|manager|operator|viewer)$")
    is_active: bool | None = None


@router.get("")
def get_users(
    current_user: dict = Depends(require_admin),
    conn: Connection = Depends(get_connection),
) -> dict[str, object]:
    return {"items": to_jsonable(list_users(conn))}


@router.post("")
def post_user(
    payload: UserCreateRequest,
    current_user: dict = Depends(require_admin),
    conn: Connection = Depends(get_connection),
) -> dict[str, object]:
    try:
        user = create_user(
            conn,
            account=payload.account,
            display_name=payload.display_name,
            password=payload.password,
            role=payload.role,
            is_active=payload.is_active,
        )
    except errors.UniqueViolation as exc:
        conn.rollback()
        raise HTTPException(status_code=409, detail="Account already exists") from exc
    return {"user": to_jsonable(user)}


@router.patch("/{user_id}")
def patch_user(
    user_id: int,
    payload: UserUpdateRequest,
    current_user: dict = Depends(require_admin),
    conn: Connection = Depends(get_connection),
) -> dict[str, object]:
    user = update_user(
        conn,
        user_id,
        display_name=payload.display_name,
        password=payload.password,
        role=payload.role,
        is_active=payload.is_active,
    )
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"user": to_jsonable(user)}
