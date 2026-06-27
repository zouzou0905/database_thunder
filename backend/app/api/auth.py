from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from psycopg import Connection

from app.api.deps import get_current_user
from app.core.security import create_access_token
from app.db import get_connection
from app.services.users import authenticate_user
from app.utils.json import to_jsonable


router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    account: str
    password: str


@router.post("/login")
def login(payload: LoginRequest, conn: Connection = Depends(get_connection)) -> dict[str, object]:
    user = authenticate_user(conn, payload.account, payload.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid account or password")
    return {
        "access_token": create_access_token(user),
        "token_type": "bearer",
        "user": to_jsonable(user),
    }


@router.get("/me")
def me(current_user: Annotated[dict, Depends(get_current_user)]) -> dict[str, object]:
    return {"user": to_jsonable(current_user)}
