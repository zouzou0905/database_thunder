from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from psycopg import Connection

from admin.app.core.auth import get_current_admin
from admin.app.core.config import get_admin_settings
from admin.app.db import get_connection
from backend.app.core.security import verify_password
from backend.app.services.users import get_user_by_account

router = APIRouter(prefix="/admin", tags=["admin-auth"])
templates = Jinja2Templates(directory=str(get_admin_settings().templates_dir))


@router.get("/login")
def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html")


@router.post("/login")
def login(
    request: Request,
    account: str = Form(...),
    password: str = Form(...),
    conn: Connection = Depends(get_connection),
):
    user = get_user_by_account(conn, account)
    if not user or not user["is_active"] or user["role"] != "admin":
        return templates.TemplateResponse(
            request, "login.html",
            {"error": "账号不存在、已停用或非管理员", "account": account},
            status_code=401,
        )
    if not verify_password(password, user["password_hash"]):
        return templates.TemplateResponse(
            request, "login.html",
            {"error": "密码不正确", "account": account},
            status_code=401,
        )
    request.session["admin_user"] = {
        "id": user["id"],
        "account": user["account"],
        "display_name": user["display_name"],
        "role": user["role"],
    }
    return RedirectResponse(url="/admin/", status_code=303)


@router.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/admin/login", status_code=303)
