from __future__ import annotations

from collections.abc import Iterator

import psycopg
from psycopg.rows import dict_row

from app.pool import get_pool


def get_connection() -> Iterator[psycopg.Connection]:
    """Yield a connection from the application pool.

    The connection is returned to the pool when the context manager exits.
    """
    pool = get_pool()
    with pool.connection() as conn:
        conn.row_factory = dict_row
        conn.execute("SET statement_timeout = '30s'")  # prevent runaway queries from blocking the pool
        conn.execute("SET lock_timeout = '5s'")       # don't hang if a background refresh holds a lock
        yield conn
