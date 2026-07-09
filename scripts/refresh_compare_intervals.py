"""Refresh keyword_compare_interval_snapshot for common date intervals.

This is the LOGGED replacement for the UNLOGGED keyword_compare_range_cache.
Populates pre-computed snapshots for high-value intervals that survive
PostgreSQL restarts.
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
from app.services.keyword_compare_intervals import (
    CompareInterval,
    refresh_interval_snapshot,
)


def ensure_schema(conn: psycopg.Connection) -> None:
    schema_path = ROOT / "sql" / "schema" / "013_keyword_compare_interval_snapshot.sql"
    with conn.cursor() as cur:
        cur.execute(schema_path.read_text(encoding="utf-8"))
    conn.commit()


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


def build_intervals(months: list[date]) -> list[CompareInterval]:
    sorted_months = sorted(months)
    available = {month_key(m) for m in sorted_months}
    intervals: list[CompareInterval] = []

    # Holiday windows per year
    years = sorted({m.year for m in sorted_months})
    for year in years:
        halloween_start = f"{year}-08"
        halloween_end = f"{year}-10"
        if halloween_start in available and halloween_end in available:
            intervals.append(
                CompareInterval(
                    code=f"halloween_{year}",
                    name=f"Halloween {year}",
                    start_month=date(year, 8, 1),
                    end_month=date(year, 10, 1),
                )
            )

        christmas_start = f"{year}-10"
        christmas_end = f"{year}-12"
        if christmas_start in available and christmas_end in available:
            intervals.append(
                CompareInterval(
                    code=f"christmas_{year}",
                    name=f"Christmas {year}",
                    start_month=date(year, 10, 1),
                    end_month=date(year, 12, 1),
                )
            )

    # Recent windows
    if len(sorted_months) >= 3:
        intervals.append(
            CompareInterval(
                code="recent_3m",
                name="Recent 3 months",
                start_month=sorted_months[-3],
                end_month=sorted_months[-1],
            )
        )
    if len(sorted_months) >= 6:
        intervals.append(
            CompareInterval(
                code="recent_6m",
                name="Recent 6 months",
                start_month=sorted_months[-6],
                end_month=sorted_months[-1],
            )
        )

    return intervals


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh keyword compare interval snapshots.")
    parser.add_argument("--marketplace", default="UK")
    parser.add_argument("--timeout", default="600s")
    args = parser.parse_args()

    load_env_file()
    settings = get_settings()
    conn = psycopg.connect(settings.database_url, row_factory=dict_row)
    conn.autocommit = False

    try:
        ensure_schema(conn)

        months = get_imported_months(conn, args.marketplace)
        if not months:
            print("ERROR: No imported months found.")
            return 1

        print(f"Found {len(months)} months: {months[0]} to {months[-1]}")
        intervals = build_intervals(months)
        print(f"Will refresh {len(intervals)} intervals:")
        for iv in intervals:
            print(f"  - {iv.code}: {iv.start_month} to {iv.end_month}")
        print()

        success = 0
        failed = 0
        t_start = time.time()

        for index, iv in enumerate(intervals, start=1):
            label = f"{iv.code} {iv.start_month}~{iv.end_month}"
            print(f"[{index}/{len(intervals)}] {label} ... ", end="", flush=True)
            t0 = time.time()
            try:
                count = refresh_interval_snapshot(
                    conn,
                    iv,
                    marketplace=args.marketplace,
                    statement_timeout=args.timeout,
                )
                elapsed = time.time() - t0
                print(f"OK ({elapsed:.0f}s) — {count:,} rows", flush=True)
                success += 1
            except Exception as exc:
                conn.rollback()
                elapsed = time.time() - t0
                print(f"FAILED after {elapsed:.0f}s: {exc}", flush=True)
                failed += 1

        t_total = time.time() - t_start
        print(f"\n{'=' * 50}")
        print(f"Completed: {success} succeeded, {failed} failed in {t_total / 60:.1f} minutes")

        # Verify
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT interval_code, start_month, end_month, COUNT(*) AS n
                FROM keyword_compare_interval_snapshot
                WHERE marketplace = %s
                GROUP BY 1, 2, 3
                ORDER BY 2, 3
                """,
                [args.marketplace],
            )
            rows = cur.fetchall()
        print(f"Total intervals: {len(rows)}")
        for r in rows:
            print(f"  {r['interval_code']:20s} {r['start_month']} -> {r['end_month']}: {r['n']:,} rows")

        return 0 if failed == 0 else 2
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
