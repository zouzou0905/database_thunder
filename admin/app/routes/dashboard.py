from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from psycopg import Connection

from admin.app.core.auth import get_current_admin
from admin.app.core.config import get_admin_settings
from admin.app.db import get_connection

router = APIRouter(prefix="/admin", tags=["admin-dashboard"])
templates = Jinja2Templates(directory=str(get_admin_settings().templates_dir))


@router.get("/")
def dashboard(
    request: Request,
    admin=Depends(get_current_admin),
    conn: Connection = Depends(get_connection),
):
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) AS total FROM app_users")
        total_users = cur.fetchone()["total"]
        cur.execute("SELECT COUNT(*) AS total FROM app_users WHERE is_active = TRUE")
        active_users = cur.fetchone()["total"]
        cur.execute("SELECT COUNT(*) AS total FROM app_users WHERE role = 'admin'")
        admin_count = cur.fetchone()["total"]
        cur.execute(
            "SELECT COUNT(*) AS total FROM error_logs WHERE resolved = FALSE"
        )
        unresolved_errors = cur.fetchone()["total"]
        cur.execute(
            """
            SELECT id, account, display_name, role, is_active, created_at
            FROM app_users
            ORDER BY created_at DESC
            LIMIT 5
            """
        )
        recent_users = cur.fetchall()
        cur.execute(
            """
            SELECT id, level, endpoint, message, created_at
            FROM error_logs
            WHERE resolved = FALSE
            ORDER BY created_at DESC
            LIMIT 5
            """
        )
        recent_errors = cur.fetchall()

    return templates.TemplateResponse(
        request, "dashboard.html",
        {
            "admin": admin,
            "total_users": total_users,
            "active_users": active_users,
            "admin_count": admin_count,
            "unresolved_errors": unresolved_errors,
            "recent_users": recent_users,
            "recent_errors": recent_errors,
        },
    )
