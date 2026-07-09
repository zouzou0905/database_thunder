"""Compute keyword holiday tags from the holiday lexicon.

The keyword compare API reads from keyword_holiday_tags; it does not do
real-time holiday term matching. Current business rules:

- Halloween: keyword/translation matches the configured Halloween terms and
  the complete Aug-Oct window is rising.
- Christmas: keyword/translation matches the configured Christmas terms and
  the complete Oct-Dec window is rising.

Rows that only match a term but do not rise in the holiday window are not
written to the cache.
"""
from __future__ import annotations

import json
import re
from collections.abc import Sequence

import psycopg


SUPPORTED_HOLIDAY_CODES = {"halloween", "christmas"}


def refresh_holiday_tags(
    conn: psycopg.Connection,
    *,
    marketplace: str,
) -> int:
    """Rebuild keyword_holiday_tags for the supported holidays."""
    with conn.cursor() as cur:
        cur.execute("SET LOCAL statement_timeout = '600s'")

    events = _load_active_events(conn, marketplace)
    if not events:
        return 0

    with conn.cursor() as cur:
        cur.execute(
            """
            DELETE FROM keyword_holiday_tags
            WHERE marketplace = %s
              AND holiday_code = ANY(%s)
            """,
            [marketplace, list(SUPPORTED_HOLIDAY_CODES)],
        )

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                EXTRACT(YEAR FROM MIN(data_month))::int AS min_year,
                EXTRACT(YEAR FROM MAX(data_month))::int AS max_year
            FROM keyword_monthly_metrics
            WHERE marketplace = %s
            """,
            [marketplace],
        )
        row = cur.fetchone()
        if not row or row["min_year"] is None:
            conn.commit()
            return 0
        min_year, max_year = row["min_year"], row["max_year"]

    keywords = _load_keyword_texts(conn, marketplace)

    if not keywords:
        conn.commit()
        return 0

    needed_months = _event_month_numbers(events)
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT keyword_id, data_month, search_volume
            FROM keyword_monthly_metrics
            WHERE marketplace = %s
              AND EXTRACT(MONTH FROM data_month)::int = ANY(%s)
              AND search_volume IS NOT NULL
            ORDER BY keyword_id, data_month
            """,
            [marketplace, needed_months],
        )
        monthly_rows = cur.fetchall()

    monthly: dict[int, dict[str, float]] = {}
    for row in monthly_rows:
        month_str = row["data_month"].isoformat()[:7]
        monthly.setdefault(row["keyword_id"], {})[month_str] = float(row["search_volume"])

    event_patterns = _build_patterns(events)
    tags_to_insert: list[dict] = []

    for kw in keywords:
        kid = kw["keyword_id"]
        kw_monthly = monthly.get(kid, {})
        if not kw_monthly:
            continue

        for event in events:
            code = event["code"]
            patterns = event_patterns.get(code)
            if not patterns:
                continue

            matched_terms, match_sources = _match_keyword(
                kw["keyword"], kw["keyword_translation"], patterns
            )
            if not matched_terms:
                continue

            for year in range(min_year, max_year + 1):
                window_months = _trend_window_months(
                    year,
                    event["trend_start_month"],
                    event["trend_end_month"],
                )
                if not all(month in kw_monthly for month in window_months):
                    continue

                start_vol = kw_monthly[window_months[0]]
                end_vol = kw_monthly[window_months[-1]]
                if start_vol <= 0 or end_vol <= start_vol:
                    continue

                growth = (end_vol - start_vol) / start_vol
                tags_to_insert.append({
                    "keyword_id": kid,
                    "marketplace": marketplace,
                    "holiday_event_id": event["id"],
                    "holiday_code": code,
                    "holiday_name_cn": event["name_cn"],
                    "confidence": "confirmed",
                    "matched_terms": matched_terms,
                    "match_sources": match_sources,
                    "trend_year": year,
                    "trend_start_month": event["trend_start_month"],
                    "trend_end_month": event["trend_end_month"],
                    "start_volume": start_vol,
                    "end_volume": end_vol,
                    "growth_rate": round(growth, 4),
                    "is_trend_confirmed": True,
                })

    if not tags_to_insert:
        conn.commit()
        return 0

    with conn.cursor() as cur:
        for tag in tags_to_insert:
            cur.execute(
                """
                INSERT INTO keyword_holiday_tags (
                    keyword_id, marketplace, holiday_event_id, holiday_code,
                    holiday_name_cn, confidence, matched_terms, match_sources,
                    trend_year, trend_start_month, trend_end_month,
                    start_volume, end_volume, growth_rate, is_trend_confirmed
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (keyword_id, marketplace, holiday_event_id, trend_year)
                DO UPDATE SET
                    holiday_code = EXCLUDED.holiday_code,
                    holiday_name_cn = EXCLUDED.holiday_name_cn,
                    confidence = EXCLUDED.confidence,
                    matched_terms = EXCLUDED.matched_terms,
                    match_sources = EXCLUDED.match_sources,
                    trend_start_month = EXCLUDED.trend_start_month,
                    trend_end_month = EXCLUDED.trend_end_month,
                    start_volume = EXCLUDED.start_volume,
                    end_volume = EXCLUDED.end_volume,
                    growth_rate = EXCLUDED.growth_rate,
                    is_trend_confirmed = EXCLUDED.is_trend_confirmed,
                    updated_at = NOW()
                """,
                [
                    tag["keyword_id"],
                    tag["marketplace"],
                    tag["holiday_event_id"],
                    tag["holiday_code"],
                    tag["holiday_name_cn"],
                    tag["confidence"],
                    json.dumps(tag["matched_terms"], ensure_ascii=False),
                    json.dumps(tag["match_sources"], ensure_ascii=False),
                    tag["trend_year"],
                    tag["trend_start_month"],
                    tag["trend_end_month"],
                    tag["start_volume"],
                    tag["end_volume"],
                    tag["growth_rate"],
                    tag["is_trend_confirmed"],
                ],
            )
    conn.commit()
    return len(tags_to_insert)


def _load_active_events(conn: psycopg.Connection, marketplace: str) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT e.*, t.id AS term_id, t.term, t.term_normalized, t.match_type
            FROM holiday_events e
            JOIN holiday_terms t ON t.event_id = e.id AND t.is_active
            WHERE e.is_active
              AND e.marketplace = %s
              AND e.code = ANY(%s)
            ORDER BY e.code, t.term_normalized
            """,
            [marketplace, list(SUPPORTED_HOLIDAY_CODES)],
        )
        rows = cur.fetchall()

    events: dict[int, dict] = {}
    for r in rows:
        eid = r["id"]
        if eid not in events:
            events[eid] = {
                "id": eid,
                "code": r["code"],
                "name_cn": r["name_cn"],
                "trend_start_month": r["trend_start_month"],
                "trend_end_month": r["trend_end_month"],
                "terms": [],
            }
        events[eid]["terms"].append({
            "term": r["term"],
            "normalized": r["term_normalized"],
            "match_type": r["match_type"],
        })
    return list(events.values())


def _load_keyword_texts(conn: psycopg.Connection, marketplace: str) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT keyword_id, keyword, keyword_translation, marketplace
            FROM keyword_compare_snapshot
            WHERE marketplace = %s
            """,
            [marketplace],
        )
        rows = cur.fetchall()
    if rows:
        return rows

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT DISTINCT ON (m.keyword_id)
                k.id AS keyword_id,
                k.keyword_normalized AS keyword,
                m.keyword_translation,
                m.marketplace
            FROM keyword_monthly_metrics m
            JOIN keywords k ON k.id = m.keyword_id
            WHERE m.marketplace = %s
            ORDER BY m.keyword_id, m.data_month DESC
            """,
            [marketplace],
        )
        return cur.fetchall()


def _event_month_numbers(events: Sequence[dict]) -> list[int]:
    months: set[int] = set()
    for event in events:
        start_month = event["trend_start_month"]
        end_month = event["trend_end_month"]
        if start_month <= end_month:
            months.update(range(start_month, end_month + 1))
        else:
            months.update(range(start_month, 13))
            months.update(range(1, end_month + 1))
    return sorted(months)


def _trend_window_months(year: int, start_month: int, end_month: int) -> list[str]:
    if start_month <= end_month:
        return [f"{year}-{month:02d}" for month in range(start_month, end_month + 1)]
    return (
        [f"{year}-{month:02d}" for month in range(start_month, 13)]
        + [f"{year + 1}-{month:02d}" for month in range(1, end_month + 1)]
    )


def _build_patterns(events: Sequence[dict]) -> dict[str, list[dict]]:
    result: dict[str, list[dict]] = {}
    for event in events:
        patterns: list[dict] = []
        for term in event["terms"]:
            escaped = re.escape(term["normalized"])
            if term["match_type"] == "word":
                regex = re.compile(rf"(?<![a-z]){escaped}(?![a-z])", re.IGNORECASE)
            else:
                regex = re.compile(escaped, re.IGNORECASE)
            patterns.append({
                "term": term["term"],
                "normalized": term["normalized"],
                "regex": regex,
            })
        result[event["code"]] = patterns
    return result


def _match_keyword(
    keyword: str,
    translation: str | None,
    patterns: Sequence[dict],
) -> tuple[list[str], list[str]]:
    matched_terms: list[str] = []
    match_sources: list[str] = []

    texts = [("keyword", keyword)]
    if translation:
        texts.append(("translation", translation))

    seen: set[str] = set()
    for source, text in texts:
        if not text:
            continue
        text_lower = text.lower()
        for pattern in patterns:
            if pattern["term"] in seen:
                continue
            if pattern["regex"].search(text_lower):
                seen.add(pattern["term"])
                matched_terms.append(pattern["term"])
                if source not in match_sources:
                    match_sources.append(source)

    return matched_terms, match_sources
