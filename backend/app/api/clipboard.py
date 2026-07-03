from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from psycopg import Connection

from app.api.deps import get_current_user
from app.db import get_connection
from app.utils.json import to_jsonable


router = APIRouter(prefix="/clipboard", tags=["clipboard"])

MAX_CLIPBOARD_CONTENT_CHARS = 500_000


class ClipboardCreateRequest(BaseModel):
    title: str = Field(default="", max_length=200)
    content: str = Field(min_length=1, max_length=MAX_CLIPBOARD_CONTENT_CHARS)


@router.get("")
def list_clipboard_items(
    limit: int = Query(default=50, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    conn: Connection = Depends(get_connection),
) -> dict[str, object]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                c.id,
                c.title,
                c.content,
                c.content_size,
                c.created_by,
                u.display_name AS created_by_name,
                u.account AS created_by_account,
                c.created_at,
                c.updated_at
            FROM shared_clipboard_items c
            JOIN app_users u ON u.id = c.created_by
            ORDER BY c.created_at DESC
            LIMIT %(limit)s
            """,
            {"limit": limit},
        )
        items = cur.fetchall()
    return {"items": to_jsonable(items)}


@router.post("")
def create_clipboard_item(
    payload: ClipboardCreateRequest,
    current_user: dict = Depends(get_current_user),
    conn: Connection = Depends(get_connection),
) -> dict[str, object]:
    content = payload.content.strip("\ufeff")
    if not content.strip():
        raise HTTPException(status_code=400, detail="Clipboard content cannot be empty")

    title = payload.title.strip()
    content_size = len(content.encode("utf-8"))
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO shared_clipboard_items (
                title,
                content,
                content_size,
                created_by
            )
            VALUES (
                %(title)s,
                %(content)s,
                %(content_size)s,
                %(created_by)s
            )
            RETURNING
                id,
                title,
                content,
                content_size,
                created_by,
                created_at,
                updated_at
            """,
            {
                "title": title,
                "content": content,
                "content_size": content_size,
                "created_by": current_user["id"],
            },
        )
        item = cur.fetchone()
    conn.commit()
    return {"item": to_jsonable(item)}


@router.delete("/{item_id}")
def delete_clipboard_item(
    item_id: int,
    current_user: dict = Depends(get_current_user),
    conn: Connection = Depends(get_connection),
) -> dict[str, object]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT created_by
            FROM shared_clipboard_items
            WHERE id = %(item_id)s
            """,
            {"item_id": item_id},
        )
        item = cur.fetchone()
        if not item:
            raise HTTPException(status_code=404, detail="Clipboard item not found")
        if item["created_by"] != current_user["id"] and current_user["role"] != "admin":
            raise HTTPException(status_code=403, detail="Only the creator or admin can delete this item")

        cur.execute(
            "DELETE FROM shared_clipboard_items WHERE id = %(item_id)s",
            {"item_id": item_id},
        )
    conn.commit()
    return {"ok": True}
