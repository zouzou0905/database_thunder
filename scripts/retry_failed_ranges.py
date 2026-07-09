"""Retry the 3 failed ranges with higher statement_timeout."""
from __future__ import annotations
import sys, time
sys.path.insert(0, r"D:\database\database_thunder-main\backend")
from psycopg.rows import dict_row
from app.core.config import get_settings
from app.services.keyword_compare import (
    KeywordCompareFilters,
    _ensure_range_cache,
    _month_to_date,
)
import psycopg

settings = get_settings()
conn = psycopg.connect(settings.database_url, row_factory=dict_row)

# 3 failed ranges from the prewarm run
retry_ranges = [
    ("2025-12 (圣诞月)", "2025-12", "2025-12"),
    ("近3月 2026-02~2026-04", "2026-02", "2026-04"),
    ("近6月 2025-11~2026-04", "2025-11", "2026-04"),
]

for label, start, end in retry_ranges:
    print(f"Warming {label} ... ", end="", flush=True)
    t0 = time.time()
    try:
        _ensure_range_cache(
            conn,
            KeywordCompareFilters(start_month=start, end_month=end, marketplace="UK"),
            _month_to_date(start),
            _month_to_date(end),
            statement_timeout="300s",
        )
        conn.commit()
        elapsed = time.time() - t0
        print(f"OK ({elapsed:.0f}s)", flush=True)
    except Exception as e:
        conn.rollback()
        elapsed = time.time() - t0
        print(f"FAILED after {elapsed:.0f}s: {e}", flush=True)

# Verify
with conn.cursor() as cur:
    cur.execute("SELECT count(*) FROM keyword_compare_range_cache")
    total = cur.fetchone()["count"]
    cur.execute("SELECT DISTINCT start_month, end_month, count(*) AS n FROM keyword_compare_range_cache GROUP BY 1,2 ORDER BY 1")
    ranges = cur.fetchall()
print(f"\nFinal range_cache: {total:,} rows across {len(ranges)} ranges:")
for r in ranges:
    print(f"  {r['start_month']} -> {r['end_month']}: {r['n']:,} rows")

conn.close()
