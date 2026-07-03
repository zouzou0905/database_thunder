from __future__ import annotations

import re
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from psycopg import Connection

from app.api.deps import get_current_user, require_admin
from app.db import get_connection
from app.utils.json import to_jsonable


router = APIRouter(prefix="/holiday-lexicon", tags=["holiday-lexicon"])

CODE_RE = re.compile(r"^[a-z0-9_-]{2,40}$")


class HolidayEventCreateRequest(BaseModel):
    code: str = Field(min_length=2, max_length=40)
    name_cn: str = Field(min_length=1, max_length=80)
    name_en: str = Field(default="", max_length=80)
    marketplace: str = Field(default="UK", max_length=20)
    trend_start_month: int = Field(ge=1, le=12)
    trend_end_month: int = Field(ge=1, le=12)
    min_growth_rate: float = Field(default=0.2, ge=0, le=100)
    terms: list[str] = Field(default_factory=list)


class HolidayEventUpdateRequest(BaseModel):
    name_cn: str | None = Field(default=None, min_length=1, max_length=80)
    name_en: str | None = Field(default=None, max_length=80)
    marketplace: str | None = Field(default=None, max_length=20)
    trend_start_month: int | None = Field(default=None, ge=1, le=12)
    trend_end_month: int | None = Field(default=None, ge=1, le=12)
    min_growth_rate: float | None = Field(default=None, ge=0, le=100)
    is_active: bool | None = None


class HolidayTermsCreateRequest(BaseModel):
    terms: list[str] = Field(min_length=1, max_length=500)
    match_type: Literal["auto", "word", "phrase"] = "auto"


def _normalize_code(code: str) -> str:
    value = code.strip().lower()
    if not CODE_RE.match(value):
        raise HTTPException(status_code=400, detail="节日编码只能包含小写字母、数字、下划线和短横线")
    return value


def _normalize_terms(terms: list[str]) -> list[tuple[str, str, str]]:
    seen: set[str] = set()
    result: list[tuple[str, str, str]] = []
    for term in terms:
        display = " ".join(term.strip().split())
        if not display:
            continue
        normalized = display.lower()
        if normalized in seen:
            continue
        seen.add(normalized)
        match_type = "phrase" if " " in normalized else "word"
        result.append((display, normalized, match_type))
    return result


def _fetch_events(conn: Connection) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                e.*,
                COUNT(t.id) FILTER (WHERE t.is_active) AS active_term_count,
                COUNT(t.id) AS term_count
            FROM holiday_events e
            LEFT JOIN holiday_terms t ON t.event_id = e.id
            GROUP BY e.id
            ORDER BY e.is_active DESC, e.code
            """
        )
        events = cur.fetchall()
        cur.execute(
            """
            SELECT *
            FROM holiday_terms
            ORDER BY event_id, is_active DESC, term_normalized
            """
        )
        terms = cur.fetchall()

    terms_by_event: dict[int, list[dict]] = {}
    for term in terms:
        terms_by_event.setdefault(term["event_id"], []).append(term)
    for event in events:
        event["terms"] = terms_by_event.get(event["id"], [])
    return events


@router.get("")
def list_holiday_events(
    current_user: dict = Depends(get_current_user),
    conn: Connection = Depends(get_connection),
) -> dict[str, object]:
    return {"items": to_jsonable(_fetch_events(conn))}


@router.post("")
def create_holiday_event(
    payload: HolidayEventCreateRequest,
    current_user: dict = Depends(require_admin),
    conn: Connection = Depends(get_connection),
) -> dict[str, object]:
    code = _normalize_code(payload.code)
    terms = _normalize_terms(payload.terms)
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO holiday_events (
                code, name_cn, name_en, marketplace,
                trend_start_month, trend_end_month, min_growth_rate
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            [
                code,
                payload.name_cn.strip(),
                payload.name_en.strip(),
                payload.marketplace.strip().upper(),
                payload.trend_start_month,
                payload.trend_end_month,
                payload.min_growth_rate,
            ],
        )
        event_id = cur.fetchone()["id"]
        for display, normalized, match_type in terms:
            cur.execute(
                """
                INSERT INTO holiday_terms (event_id, term, term_normalized, match_type)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (event_id, term_normalized) DO NOTHING
                """,
                [event_id, display, normalized, match_type],
            )
    conn.commit()
    return {"items": to_jsonable(_fetch_events(conn))}


@router.patch("/{event_id}")
def update_holiday_event(
    event_id: int,
    payload: HolidayEventUpdateRequest,
    current_user: dict = Depends(require_admin),
    conn: Connection = Depends(get_connection),
) -> dict[str, object]:
    fields: list[str] = []
    params: list[object] = []
    for key in (
        "name_cn",
        "name_en",
        "marketplace",
        "trend_start_month",
        "trend_end_month",
        "min_growth_rate",
        "is_active",
    ):
        value = getattr(payload, key)
        if value is None:
            continue
        fields.append(f"{key} = %s")
        params.append(value.strip().upper() if key == "marketplace" and isinstance(value, str) else value)
    if not fields:
        raise HTTPException(status_code=400, detail="没有可更新的字段")
    fields.append("updated_at = NOW()")
    params.append(event_id)
    with conn.cursor() as cur:
        cur.execute(
            f"""
            UPDATE holiday_events
            SET {", ".join(fields)}
            WHERE id = %s
            RETURNING id
            """,
            params,
        )
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="节日不存在")
    conn.commit()
    return {"items": to_jsonable(_fetch_events(conn))}


@router.post("/{event_id}/terms")
def add_holiday_terms(
    event_id: int,
    payload: HolidayTermsCreateRequest,
    current_user: dict = Depends(require_admin),
    conn: Connection = Depends(get_connection),
) -> dict[str, object]:
    terms = _normalize_terms(payload.terms)
    if not terms:
        raise HTTPException(status_code=400, detail="词库不能为空")
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM holiday_events WHERE id = %s", [event_id])
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="节日不存在")
        for display, normalized, auto_match_type in terms:
            match_type = auto_match_type if payload.match_type == "auto" else payload.match_type
            cur.execute(
                """
                INSERT INTO holiday_terms (event_id, term, term_normalized, match_type)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (event_id, term_normalized)
                DO UPDATE SET
                    term = EXCLUDED.term,
                    match_type = EXCLUDED.match_type,
                    is_active = TRUE,
                    updated_at = NOW()
                """,
                [event_id, display, normalized, match_type],
            )
    conn.commit()
    return {"items": to_jsonable(_fetch_events(conn))}


@router.delete("/terms/{term_id}")
def delete_holiday_term(
    term_id: int,
    current_user: dict = Depends(require_admin),
    conn: Connection = Depends(get_connection),
) -> dict[str, object]:
    with conn.cursor() as cur:
        cur.execute("DELETE FROM holiday_terms WHERE id = %s RETURNING id", [term_id])
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="词条不存在")
    conn.commit()
    return {"items": to_jsonable(_fetch_events(conn))}
