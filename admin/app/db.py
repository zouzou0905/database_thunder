from __future__ import annotations

from collections.abc import Iterator

import psycopg
from psycopg.rows import dict_row

from admin.app.pool import get_pool


def get_connection() -> Iterator[psycopg.Connection]:
    pool = get_pool()
    with pool.connection() as conn:
        conn.row_factory = dict_row
        yield conn
