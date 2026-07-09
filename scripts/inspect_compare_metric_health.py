from __future__ import annotations

import psycopg

from common import get_database_url


TABLES = ("keyword_compare_snapshot", "keyword_compare_range_cache")


with psycopg.connect(get_database_url()) as conn:
    with conn.cursor() as cur:
        for table in TABLES:
            cur.execute(
                f"""
                SELECT
                    COUNT(*) AS total,
                    COUNT(search_volume_change) AS volume_change,
                    COUNT(search_volume_growth_rate) AS growth_rate,
                    COUNT(mom_rate) AS mom_rate,
                    COUNT(yoy_rate) AS yoy_rate,
                    COUNT(*) FILTER (WHERE trend_type IS DISTINCT FROM 'volatile') AS nonvolatile,
                    COUNT(*) FILTER (WHERE trend_type = 'volatile') AS volatile
                FROM {table}
                WHERE marketplace = 'UK'
                """
            )
            print(table, cur.fetchone())
