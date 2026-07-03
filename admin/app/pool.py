from __future__ import annotations

from psycopg_pool import ConnectionPool

from admin.app.core.config import get_admin_settings

_pool: ConnectionPool | None = None


def get_pool() -> ConnectionPool:
    global _pool
    if _pool is not None:
        return _pool
    settings = get_admin_settings()
    _pool = ConnectionPool(
        conninfo=settings.database_url,
        min_size=2,
        max_size=10,
        timeout=30,
        max_lifetime=3600,
        kwargs={"row_factory": None},
        open=True,
    )
    return _pool


def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None
