"""Compute keyword holiday tags by matching active holiday terms against keywords.

Writes results to keyword_holiday_tags cache table.  The keyword compare
API reads from this cache rather than doing real-time text matching.
"""
from __future__ import annotations

import re
from collections.abc import Sequence

import psycopg
from psycopg.rows import dict_row


def refresh_holiday_tags(
    conn: psycopg.Connection,
    *,
    marketplace: str,
) -> int:
    """Rebuild keyword_holiday_tags for the given marketplace.

    Returns the number of tag rows inserted.
    """
    # Disable statement_timeout for this long-running batch operation
    with conn.cursor() as cur:
        cur.execute("SET LOCAL statement_timeout = '300s'")

    events = _load_active_events(conn, marketplace)
    if not events:
        return 0

    # Clear existing tags for this marketplace
    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM keyword_holiday_tags WHERE marketplace = %s",
            [marketplace],
        )

    # Determine the data year range for trend_year assignment
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
            return 0
        min_year, max_year = row["min_year"], row["max_year"]

    # Load all keywords for this marketplace (id, keyword, translation)
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                k.id AS keyword_id,
                k.keyword_normalized AS keyword,
                m.keyword_translation,
                m.marketplace
            FROM keywords k
            JOIN keyword_monthly_metrics m
              ON m.keyword_id = k.id AND m.marketplace = %s
            GROUP BY k.id, k.keyword_normalized, m.keyword_translation, m.marketplace
            """,
            [marketplace],
        )
        keywords = cur.fetchall()

    if not keywords:
        return 0

    # Pre-load monthly search volumes for all keywords
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT keyword_id, data_month, search_volume
            FROM keyword_monthly_metrics
            WHERE marketplace = %s AND search_volume IS NOT NULL
            ORDER BY keyword_id, data_month
            """,
            [marketplace],
        )
        monthly_rows = cur.fetchall()

    # Build keyword_id -> {data_month: search_volume} map
    monthly: dict[int, dict[str, float]] = {}
    for row in monthly_rows:
        month_str = row["data_month"].isoformat()[:7]
        monthly.setdefault(row["keyword_id"], {})[month_str] = float(row["search_volume"])

    # Compile term patterns per event
    event_patterns = _build_patterns(events)

    # Match and compute tags
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

            # Determine which trend years to check
            available_months = sorted(kw_monthly.keys())
            for year in range(min_year, max_year + 1):
                start_m = event["trend_start_month"]
                end_m = event["trend_end_month"]
                s_month = f"{year}-{start_m:02d}"
                e_month = f"{year}-{end_m:02d}"

                # Find months in this trend window
                window_months = [
                    m for m in available_months
                    if s_month <= m <= e_month
                ]

                # Skip years where the trend window has zero data (future years etc.)
                if len(window_months) == 0:
                    continue

                window_volumes = [kw_monthly[m] for m in window_months]
                start_vol = window_volumes[0]
                end_vol = window_volumes[-1]

                # Only 1 month of data → suspected (hit term but can't confirm trend)
                if len(window_months) == 1:
                    tags_to_insert.append({
                        "keyword_id": kid,
                        "marketplace": marketplace,
                        "holiday_event_id": event["id"],
                        "holiday_code": code,
                        "holiday_name_cn": event["name_cn"],
                        "confidence": "suspected",
                        "matched_terms": matched_terms,
                        "match_sources": match_sources,
                        "trend_year": year,
                        "trend_start_month": start_m,
                        "trend_end_month": end_m,
                        "start_volume": start_vol,
                        "end_volume": end_vol,
                        "growth_rate": None,
                        "is_trend_confirmed": False,
                    })
                    continue

                # 2+ months but start volume invalid → suspected
                if start_vol is None or start_vol <= 0:
                    tags_to_insert.append({
                        "keyword_id": kid,
                        "marketplace": marketplace,
                        "holiday_event_id": event["id"],
                        "holiday_code": code,
                        "holiday_name_cn": event["name_cn"],
                        "confidence": "suspected",
                        "matched_terms": matched_terms,
                        "match_sources": match_sources,
                        "trend_year": year,
                        "trend_start_month": start_m,
                        "trend_end_month": end_m,
                        "start_volume": start_vol,
                        "end_volume": end_vol,
                        "growth_rate": None,
                        "is_trend_confirmed": False,
                    })
                    continue

                growth = (end_vol - start_vol) / start_vol
                trend_confirmed = _is_trend_confirmed(
                    growth, window_volumes, event["min_growth_rate"]
                )

                tags_to_insert.append({
                    "keyword_id": kid,
                    "marketplace": marketplace,
                    "holiday_event_id": event["id"],
                    "holiday_code": code,
                    "holiday_name_cn": event["name_cn"],
                    "confidence": "confirmed" if trend_confirmed else "suspected",
                    "matched_terms": matched_terms,
                    "match_sources": match_sources,
                    "trend_year": year,
                    "trend_start_month": start_m,
                    "trend_end_month": end_m,
                    "start_volume": start_vol,
                    "end_volume": end_vol,
                    "growth_rate": round(growth, 4),
                    "is_trend_confirmed": trend_confirmed,
                })

    if not tags_to_insert:
        return 0

    # Bulk insert
    import json
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
                    confidence = EXCLUDED.confidence,
                    matched_terms = EXCLUDED.matched_terms,
                    match_sources = EXCLUDED.match_sources,
                    start_volume = EXCLUDED.start_volume,
                    end_volume = EXCLUDED.end_volume,
                    growth_rate = EXCLUDED.growth_rate,
                    is_trend_confirmed = EXCLUDED.is_trend_confirmed,
                    updated_at = NOW()
                """,
                [
                    tag["keyword_id"], tag["marketplace"], tag["holiday_event_id"],
                    tag["holiday_code"], tag["holiday_name_cn"], tag["confidence"],
                    json.dumps(tag["matched_terms"], ensure_ascii=False),
                    json.dumps(tag["match_sources"], ensure_ascii=False),
                    tag["trend_year"], tag["trend_start_month"], tag["trend_end_month"],
                    tag["start_volume"], tag["end_volume"], tag["growth_rate"],
                    tag["is_trend_confirmed"],
                ],
            )
    conn.commit()
    return len(tags_to_insert)


# ── Helpers ──────────────────────────────────────────────────────

def _load_active_events(conn: psycopg.Connection, marketplace: str) -> list[dict]:
    """Load active holiday events with their active terms."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT e.*, t.id AS term_id, t.term, t.term_normalized, t.match_type
            FROM holiday_events e
            JOIN holiday_terms t ON t.event_id = e.id AND t.is_active
            WHERE e.is_active AND e.marketplace = %s
            ORDER BY e.code, t.term_normalized
            """,
            [marketplace],
        )
        rows = cur.fetchall()

    events: dict[int, dict] = {}
    for r in rows:
        eid = r["id"]
        if eid not in events:
            events[eid] = {
                "id": eid, "code": r["code"], "name_cn": r["name_cn"],
                "trend_start_month": r["trend_start_month"],
                "trend_end_month": r["trend_end_month"],
                "min_growth_rate": float(r["min_growth_rate"]),
                "terms": [],
            }
        events[eid]["terms"].append({
            "term": r["term"],
            "normalized": r["term_normalized"],
            "match_type": r["match_type"],
        })
    return list(events.values())


def _build_patterns(events: Sequence[dict]) -> dict[str, list[dict]]:
    """Compile regex patterns for each event's terms."""
    result: dict[str, list[dict]] = {}
    for event in events:
        patterns: list[dict] = []
        for t in event["terms"]:
            if t["match_type"] == "word":
                escaped = re.escape(t["normalized"])
                patterns.append({
                    "type": "word",
                    "term": t["term"],
                    "normalized": t["normalized"],
                    "regex": re.compile(rf"(?<![a-z]){escaped}(?![a-z])", re.IGNORECASE),
                })
            else:
                escaped = re.escape(t["normalized"])
                patterns.append({
                    "type": "phrase",
                    "term": t["term"],
                    "normalized": t["normalized"],
                    "regex": re.compile(escaped, re.IGNORECASE),
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
        for p in patterns:
            if p["term"] in seen:
                continue
            if p["regex"].search(text_lower):
                seen.add(p["term"])
                matched_terms.append(p["term"])
                if source not in match_sources:
                    match_sources.append(source)

    return matched_terms, match_sources


def _is_trend_confirmed(
    growth: float,
    window_volumes: Sequence[float],
    min_growth_rate: float,
) -> bool:
    """Check if the trend window meets confirmation criteria."""
    if len(window_volumes) < 2:
        return False
    start = window_volumes[0]
    end = window_volumes[-1]
    if start <= 0:
        return False
    if end <= start:
        return False
    if growth < min_growth_rate:
        return False
    # For 3+ month windows: check no sharp drop after middle peak
    if len(window_volumes) >= 3:
        mid_idx = len(window_volumes) // 2
        mid_vol = window_volumes[mid_idx]
        if mid_vol > 0 and end < mid_vol * 0.9:
            return False
    return True
