"""Pre-warm keyword_compare_range_cache for high-value compare ranges.

This script only populates the UNLOGGED range cache. It does not refresh
snapshot, product-selection cache, or trend tables.

Default ranges are intentionally multi-month and user-facing:
- Halloween window: Aug-Oct
- Christmas window: Oct-Dec
- Recent 3 months
- Recent 6 months

Single-month ranges can be included explicitly, but they are not useful for
most horizontal compare workflows.
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import date
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import get_settings, load_env_file
from app.services.keyword_compare import (
    KeywordCompareFilters,
    _ensure_range_cache,
    _month_to_date,
)


def get_imported_months(conn: psycopg.Connection, marketplace: str) -> list[date]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT DISTINCT data_month
            FROM keyword_monthly_metrics
            WHERE marketplace = %s
            ORDER BY data_month
            """,
            [marketplace],
        )
        return [row["data_month"] for row in cur.fetchall()]


def month_key(value: date) -> str:
    return value.strftime("%Y-%m")


def add_range(
    ranges: list[tuple[str, str, str]],
    seen: set[tuple[str, str]],
    label: str,
    start: str,
    end: str,
    available: set[str],
) -> None:
    start_date = _month_to_date(start)
    end_date = _month_to_date(end)
    if not start_date or not end_date:
        return
    if start_date > end_date:
        start, end = end, start
    if start not in available or end not in available:
        return
    key = (start, end)
    if key in seen:
        return
    seen.add(key)
    ranges.append((label, start, end))


def build_warmup_ranges(
    months: list[date],
    *,
    include_single_months: bool,
    include_holiday_windows: bool,
    include_recent_windows: bool,
) -> list[tuple[str, str, str]]:
    sorted_months = sorted(months)
    available = {month_key(month) for month in sorted_months}
    ranges: list[tuple[str, str, str]] = []
    seen: set[tuple[str, str]] = set()

    if include_holiday_windows:
        years = sorted({month.year for month in sorted_months})
        for year in years:
            add_range(ranges, seen, f"Halloween {year}", f"{year}-08", f"{year}-10", available)
            add_range(ranges, seen, f"Christmas {year}", f"{year}-10", f"{year}-12", available)

    if include_recent_windows:
        if len(sorted_months) >= 3:
            add_range(
                ranges,
                seen,
                "Recent 3 months",
                month_key(sorted_months[-3]),
                month_key(sorted_months[-1]),
                available,
            )
        if len(sorted_months) >= 6:
            add_range(
                ranges,
                seen,
                "Recent 6 months",
                month_key(sorted_months[-6]),
                month_key(sorted_months[-1]),
                available,
            )

    if include_single_months:
        for month in sorted_months:
            key = month_key(month)
            add_range(ranges, seen, f"Single month {key}", key, key, available)

    return ranges


def clear_single_month_ranges(conn: psycopg.Connection, marketplace: str) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            DELETE FROM keyword_compare_range_cache
            WHERE marketplace = %s
              AND start_month = end_month
            """,
            [marketplace],
        )
        deleted = cur.rowcount
    conn.commit()
    return deleted


def main() -> int:
    parser = argparse.ArgumentParser(description="Pre-warm keyword compare range cache.")
    parser.add_argument("--marketplace", default="UK")
    parser.add_argument("--timeout", default="600s", help="statement_timeout for each range")
    parser.add_argument("--include-single-months", action="store_true")
    parser.add_argument("--skip-holiday-windows", action="store_true")
    parser.add_argument("--skip-recent-windows", action="store_true")
    parser.add_argument("--clear-single-months", action="store_true")
    args = parser.parse_args()

    load_env_file()
    settings = get_settings()
    conn = psycopg.connect(settings.database_url, row_factory=dict_row)
    conn.autocommit = False

    try:
        if args.clear_single_months:
            deleted = clear_single_month_ranges(conn, args.marketplace)
            print(f"Deleted {deleted:,} single-month cache rows.")

        months = get_imported_months(conn, args.marketplace)
        if not months:
            print("ERROR: No imported months found.")
            return 1

        print(f"Found {len(months)} months: {months[0]} to {months[-1]}")
        warmup_ranges = build_warmup_ranges(
            months,
            include_single_months=args.include_single_months,
            include_holiday_windows=not args.skip_holiday_windows,
            include_recent_windows=not args.skip_recent_windows,
        )
        print(f"Will warm {len(warmup_ranges)} ranges.")
        for label, start, end in warmup_ranges:
            print(f"  - {label}: {start} to {end}")
        print()

        success = 0
        failed = 0
        t_total_start = time.time()

        for index, (label, start, end) in enumerate(warmup_ranges, start=1):
            print(f"[{index}/{len(warmup_ranges)}] {label} {start}~{end} ... ", end="", flush=True)
            t0 = time.time()
            try:
                _ensure_range_cache(
                    conn,
                    KeywordCompareFilters(start_month=start, end_month=end, marketplace=args.marketplace),
                    _month_to_date(start),
                    _month_to_date(end),
                    statement_timeout=args.timeout,
                )
                conn.commit()
                elapsed = time.time() - t0
                print(f"OK ({elapsed:.0f}s)", flush=True)
                success += 1
            except Exception as exc:
                elapsed = time.time() - t0
                print(f"FAILED after {elapsed:.0f}s: {exc}", flush=True)
                conn.rollback()
                failed += 1

        t_total = time.time() - t_total_start
        print(f"\n{'=' * 50}")
        print(f"Completed: {success} succeeded, {failed} failed in {t_total / 60:.1f} minutes")

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) AS total
                FROM keyword_compare_range_cache
                WHERE marketplace = %s
                """,
                [args.marketplace],
            )
            total = cur.fetchone()["total"]
            cur.execute(
                """
                SELECT start_month, end_month, COUNT(*) AS n
                FROM keyword_compare_range_cache
                WHERE marketplace = %s
                GROUP BY 1, 2
                ORDER BY 1, 2
                """,
                [args.marketplace],
            )
            ranges = cur.fetchall()

        print(f"range_cache total rows: {total:,}")
        print(f"Cached ranges: {len(ranges)}")
        for row in ranges:
            print(f"  {row['start_month']} -> {row['end_month']}: {row['n']:,} rows")
        return 0 if failed == 0 else 2
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
