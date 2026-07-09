from __future__ import annotations

import psycopg

from common import get_database_url


with psycopg.connect(get_database_url()) as conn:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                pid,
                state,
                wait_event_type,
                wait_event,
                now() - query_start AS age,
                left(query, 220) AS query
            FROM pg_stat_activity
            WHERE datname = current_database()
            ORDER BY query_start NULLS LAST
            """
        )
        for row in cur.fetchall():
            print(row)
