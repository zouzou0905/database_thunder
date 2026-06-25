from __future__ import annotations

import atexit
import logging

from psycopg_pool import ConnectionPool

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_pool: ConnectionPool | None = None


def get_pool() -> ConnectionPool:
    """Return the application-wide connection pool, creating it on first call."""
    global _pool
    if _pool is not None:
        return _pool

    settings = get_settings()
    _pool = ConnectionPool(
        conninfo=settings.database_url,
        min_size=2,
        max_size=30,            # 10 concurrent ops × 2-3 queries = 20-30 connections worst-case
        timeout=30,             # wait up to 30s for a connection before raising PoolTimeout
        max_lifetime=3600,      # recycle connections older than 1 hour (prevents stale connections)
        kwargs={"row_factory": None},  # row_factory is set per-cursor in the app
        open=True,
    )
    atexit.register(_pool.close)
    logger.info("Connection pool created (min=2, max=30, lifetime=3600s)")
    return _pool


def close_pool() -> None:
    """Gracefully close the connection pool (called on application shutdown)."""
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None
        logger.info("Connection pool closed")
