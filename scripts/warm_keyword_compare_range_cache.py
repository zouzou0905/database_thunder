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

from app.services.keyword_compare import KeywordCompareFilters, _ensure_range_cache  # noqa: E402
from common import get_database_url  # noqa: E402


def parse_month(value: str) -> date:
    text = value.strip()
    if len(text) == 7:
        text = f"{text}-01"
    return date.fromisoformat(text)


def main() -> None:
    parser = argparse.ArgumentParser(description="Warm keyword compare exact range cache.")
    parser.add_argument("--marketplace", default="UK")
    parser.add_argument("--start-month", required=True, help="YYYY-MM or YYYY-MM-DD")
    parser.add_argument("--end-month", required=True, help="YYYY-MM or YYYY-MM-DD")
    args = parser.parse_args()

    filters = KeywordCompareFilters(
        marketplace=args.marketplace,
        start_month=args.start_month,
        end_month=args.end_month,
    )
    started = time.perf_counter()
    with psycopg.connect(get_database_url(), row_factory=dict_row) as conn:
        _ensure_range_cache(
            conn,
            filters,
            parse_month(args.start_month),
            parse_month(args.end_month),
        )
    print(
        f"Warmed keyword_compare_range_cache for {args.marketplace} "
        f"{args.start_month}..{args.end_month} in {time.perf_counter() - started:.2f}s"
    )


if __name__ == "__main__":
    main()
