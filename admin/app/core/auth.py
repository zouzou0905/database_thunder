from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.responses import RedirectResponse
from psycopg.rows import dict_row

from admin.app.pool import get_pool


class AuthRequired(Exception):
    """Raised when the user is not authenticated — caught by exception handler."""


def get_current_admin(request: Request) -> dict[str, Any]:
    """从 session 读取 admin 用户，并验证其仍然有效。"""
    user = request.session.get("admin_user")
    if not user:
        raise AuthRequired()

    pool = get_pool()
    with pool.connection() as conn:
        conn.row_factory = dict_row
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, account, display_name, role, is_active
                FROM app_users
                WHERE id = %s
                """,
                [user["id"]],
            )
            row = cur.fetchone()

    if not row or not row["is_active"] or row["role"] != "admin":
        request.session.clear()
        raise AuthRequired()

    return row

