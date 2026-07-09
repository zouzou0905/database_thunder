from __future__ import annotations

import argparse

import psycopg

from common import get_database_url
from app.services.keyword_compare_snapshot import refresh_compare_snapshot


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh keyword_compare_snapshot only.")
    parser.add_argument("--marketplace", default="UK")
    args = parser.parse_args()

    with psycopg.connect(get_database_url()) as conn:
        row_count = refresh_compare_snapshot(conn, marketplace=args.marketplace)
        conn.commit()
        print(f"Refreshed {args.marketplace} compare snapshot: {row_count} rows.", flush=True)


if __name__ == "__main__":
    main()
