from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from psycopg import Connection
from pydantic import BaseModel

from admin.app.core.auth import get_current_admin
from admin.app.core.config import get_admin_settings
from admin.app.db import get_connection
from backend.app.services.users import (
    create_user,
    delete_user,
    get_user_by_id,
    list_users,
    update_user,
)

router = APIRouter(prefix="/admin/users", tags=["admin-users"])
templates = Jinja2Templates(directory=str(get_admin_settings().templates_dir))

ROLES = ["admin", "manager", "operator", "viewer"]


class CreateUserPayload(BaseModel):
    account: str
    display_name: str
    password: str
    role: Literal["admin", "manager", "operator", "viewer"] = "operator"


@router.get("")
def user_list(
    request: Request,
    admin=Depends(get_current_admin),
    conn: Connection = Depends(get_connection),
):
    users = list_users(conn)
    return templates.TemplateResponse(
        request, "users/list.html",
        {"admin": admin, "users": users},
    )


@router.get("/create")
def create_form(request: Request, admin=Depends(get_current_admin)):
    return templates.TemplateResponse(
        request, "users/create.html",
        {"admin": admin, "roles": ROLES},
    )


@router.post("")
def create(
    payload: CreateUserPayload,
    admin=Depends(get_current_admin),
    conn: Connection = Depends(get_connection),
):
    try:
        create_user(
            conn, account=payload.account, display_name=payload.display_name,
            password=payload.password, role=payload.role,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return RedirectResponse(url="/admin/users", status_code=303)


@router.get("/{user_id}/edit")
def edit_form(
    user_id: int,
    request: Request,
    admin=Depends(get_current_admin),
    conn: Connection = Depends(get_connection),
):
    user = get_user_by_id(conn, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return templates.TemplateResponse(
        request, "users/edit.html",
        {"admin": admin, "user": user, "roles": ROLES},
    )


class UpdateUserPayload(BaseModel):
    display_name: str
    role: Literal["admin", "manager", "operator", "viewer"]
    is_active: Literal["true", "false"] = "true"
    new_password: str = ""


@router.post("/{user_id}")
def update(
    user_id: int,
    payload: UpdateUserPayload,
    admin=Depends(get_current_admin),
    conn: Connection = Depends(get_connection),
):
    kwargs: dict = {
        "display_name": payload.display_name,
        "role": payload.role,
        "is_active": payload.is_active == "true",
    }
    if payload.new_password.strip():
        kwargs["password"] = payload.new_password.strip()
    update_user(conn, user_id, **kwargs)
    return RedirectResponse(url="/admin/users", status_code=303)


@router.post("/{user_id}/toggle")
def toggle_active(
    user_id: int,
    admin=Depends(get_current_admin),
    conn: Connection = Depends(get_connection),
):
    user = get_user_by_id(conn, user_id)
    if not user:
        raise HTTPException(status_code=404)
    update_user(conn, user_id, is_active=not user["is_active"])
    return RedirectResponse(url="/admin/users", status_code=303)


@router.post("/{user_id}/delete")
def delete(
    user_id: int,
    request: Request,
    admin=Depends(get_current_admin),
    conn: Connection = Depends(get_connection),
):
    if user_id == admin["id"]:
        users = list_users(conn)
        return templates.TemplateResponse(
            request,
            "users/list.html",
            {
                "admin": admin,
                "users": users,
                "error": "不能删除当前登录的管理员账号，请先使用其他管理员账号操作。",
            },
            status_code=400,
        )
    deleted = delete_user(conn, user_id)
    if not deleted:
        raise HTTPException(status_code=404)
    return RedirectResponse(url="/admin/users", status_code=303)
