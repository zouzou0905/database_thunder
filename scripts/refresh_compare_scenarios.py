from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import get_settings, load_env_file
from app.services.keyword_compare_scenarios import refresh_holiday_compare_scenarios


def ensure_schema(conn: psycopg.Connection) -> None:
    schema_path = ROOT / "sql" / "schema" / "012_keyword_compare_scenario_snapshot.sql"
    with conn.cursor() as cur:
        cur.execute(schema_path.read_text(encoding="utf-8"))
    conn.commit()


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh fixed compare scenario snapshots.")
    parser.add_argument("--marketplace", default="UK")
    parser.add_argument("--timeout", default="300s")
    args = parser.parse_args()

    load_env_file()
    settings = get_settings()
    conn = psycopg.connect(settings.database_url, row_factory=dict_row)
    conn.autocommit = False
    try:
        ensure_schema(conn)
        started = time.time()
        results = refresh_holiday_compare_scenarios(
            conn,
            marketplace=args.marketplace,
            statement_timeout=args.timeout,
        )
        for result in results:
            status = "OK" if result["ok"] else "FAILED"
            print(
                f"{status} {result['scenario_code']} "
                f"{result['start_month']}~{result['end_month']}: {result['rows']:,} rows"
            )
            if not result["ok"]:
                print(f"  {result.get('error', '')}")
        print(f"Completed in {(time.time() - started):.1f}s")
        return 0 if all(result["ok"] for result in results) else 2
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
