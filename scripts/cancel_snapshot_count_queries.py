from __future__ import annotations

import psycopg

from common import get_database_url


TARGET_QUERIES = {
    "select count(*) from keyword_compare_snapshot",
    "SELECT count(*) FROM keyword_compare_snapshot",
    "select count(*) from keyword_compare_range_cache",
    "SELECT count(*) FROM keyword_compare_range_cache",
}


with psycopg.connect(get_database_url()) as conn:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT pid
            FROM pg_stat_activity
            WHERE datname = current_database()
              AND query = ANY(%s)
            """,
            (list(TARGET_QUERIES),),
        )
        pids = [row[0] for row in cur.fetchall()]
        print(f"cancel_count_pids={pids}")
        for pid in pids:
            cur.execute("SELECT pg_cancel_backend(%s)", (pid,))
            print(f"pid={pid} cancelled={cur.fetchone()[0]}")
