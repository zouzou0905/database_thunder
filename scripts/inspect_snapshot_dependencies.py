from __future__ import annotations

import psycopg

from common import get_database_url


with psycopg.connect(get_database_url()) as conn:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT dependent_ns.nspname, dependent_view.relname, dependent_view.relkind
            FROM pg_depend d
            JOIN pg_rewrite r ON r.oid = d.objid
            JOIN pg_class dependent_view ON dependent_view.oid = r.ev_class
            JOIN pg_namespace dependent_ns ON dependent_ns.oid = dependent_view.relnamespace
            WHERE d.refobjid = 'keyword_compare_snapshot'::regclass
            ORDER BY 1, 2
            """
        )
        for row in cur.fetchall():
            print(row)
