from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from psycopg import Connection

from admin.app.core.auth import get_current_admin
from admin.app.core.config import get_admin_settings
from admin.app.db import get_connection

router = APIRouter(prefix="/admin/error-logs", tags=["admin-errors"])
templates = Jinja2Templates(directory=str(get_admin_settings().templates_dir))


@router.get("")
def list_errors(
    request: Request,
    page: int = 1,
    level: str = "",
    resolved: str = "",
    admin=Depends(get_current_admin),
    conn: Connection = Depends(get_connection),
):
    page_size = 50
    offset = (page - 1) * page_size

    where = ["1=1"]
    params: dict = {"limit": page_size, "offset": offset}

    if level:
        where.append("level = %(level)s")
        params["level"] = level
    if resolved == "yes":
        where.append("resolved = TRUE")
    elif resolved == "no":
        where.append("resolved = FALSE")

    where_sql = " AND ".join(where)
    count_params = {k: v for k, v in params.items() if k not in ("limit", "offset")}

    with conn.cursor() as cur:
        cur.execute(
            f"SELECT COUNT(*) AS total FROM error_logs WHERE {where_sql}",
            count_params,
        )
        total = cur.fetchone()["total"]

        cur.execute(
            f"""
            SELECT id, level, source, endpoint, method, status_code,
                   message, user_account, resolved, created_at
            FROM error_logs
            WHERE {where_sql}
            ORDER BY created_at DESC
            LIMIT %(limit)s OFFSET %(offset)s
            """,
            params,
        )
        items = cur.fetchall()

    total_pages = (total + page_size - 1) // page_size

    return templates.TemplateResponse(
        request, "error_logs/list.html",
        {
            "admin": admin,
            "items": items,
            "page": page,
            "total_pages": total_pages,
            "total": total,
            "level": level,
            "resolved": resolved,
        },
    )


@router.get("/{error_id}")
def error_detail(
    error_id: int,
    request: Request,
    admin=Depends(get_current_admin),
    conn: Connection = Depends(get_connection),
):
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM error_logs WHERE id = %s", [error_id])
        error = cur.fetchone()
    if not error:
        raise HTTPException(status_code=404)
    return templates.TemplateResponse(
        request, "error_logs/detail.html",
        {"admin": admin, "error": error},
    )


@router.post("/{error_id}/resolve")
def toggle_resolve(
    error_id: int,
    admin=Depends(get_current_admin),
    conn: Connection = Depends(get_connection),
):
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE error_logs SET resolved = NOT resolved WHERE id = %s",
            [error_id],
        )
    conn.commit()
    return RedirectResponse(url=f"/admin/error-logs/{error_id}", status_code=303)
