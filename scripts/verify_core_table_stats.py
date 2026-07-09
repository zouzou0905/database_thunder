from __future__ import annotations

import psycopg

from common import get_database_url


TABLES = (
    "keyword_monthly_metrics",
    "keyword_compare_snapshot",
    "keyword_compare_range_cache",
    "keyword_selection_candidates_monthly",
    "keywords",
)


with psycopg.connect(get_database_url()) as conn:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT c.relname, c.reltuples::bigint, s.last_analyze, s.last_autoanalyze
            FROM pg_class c
            LEFT JOIN pg_stat_user_tables s ON s.relid = c.oid
            WHERE c.relname = ANY(%s)
            ORDER BY c.relname
            """,
            (list(TABLES),),
        )
        for row in cur.fetchall():
            print(row)
