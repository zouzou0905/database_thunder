from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import psycopg

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from calculate_trends import get_imported_months
from common import get_database_url, parse_month


def refresh_month(conn: psycopg.Connection, analysis_month, marketplace: str) -> int:
    from app.services.product_selection_cache import refresh_cache

    return refresh_cache(
        conn,
        analysis_month=analysis_month.isoformat(),
        marketplace=marketplace,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh precomputed product selection candidate cache.")
    parser.add_argument("--analysis-month", help="Analysis month, format YYYY-MM.")
    parser.add_argument("--all", action="store_true", help="Refresh all imported months in chronological order.")
    parser.add_argument("--from-month", help="Optional start month for --all, format YYYY-MM.")
    parser.add_argument("--to-month", help="Optional end month for --all, format YYYY-MM.")
    parser.add_argument("--year", type=int, help="Optional year filter for --all, for example 2026.")
    parser.add_argument("--marketplace", default="UK")
    args = parser.parse_args()

    if not args.all and not args.analysis_month:
        parser.error("Either --analysis-month or --all is required.")
    if args.all and args.analysis_month:
        parser.error("--analysis-month cannot be used together with --all.")

    with psycopg.connect(get_database_url()) as conn:
        if args.all:
            months = get_imported_months(
                conn,
                args.marketplace,
                parse_month(args.from_month) if args.from_month else None,
                parse_month(args.to_month) if args.to_month else None,
                args.year,
            )
            if not months:
                raise RuntimeError("No imported months found for the selected filters.")
        else:
            months = [parse_month(args.analysis_month)]

        for month in months:
            started = time.perf_counter()
            row_count = refresh_month(conn, month, args.marketplace)
            conn.commit()
            elapsed = time.perf_counter() - started
            print(f"Refreshed {month:%Y-%m} {args.marketplace}: {row_count} rows in {elapsed:.1f}s.")


if __name__ == "__main__":
    main()
