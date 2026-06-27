"""Manual cache-refresh utilities.

These are NOT auto-started on application boot.  Cache-table refreshes
are expensive operations that should be run deliberately — either via the
existing CLI scripts (``scripts/calculate_trends.py``,
``scripts/refresh_product_selection_cache.py``) or by calling
``cache_refresh_loop()`` from a standalone script / cron job.

If you want the app to refresh caches on a schedule, launch this loop
from a separate long-running process, not from inside the FastAPI worker::

    python -c "
    import asyncio
    from app.services.scheduler import cache_refresh_loop
    asyncio.run(cache_refresh_loop())
    "
"""

from __future__ import annotations

import asyncio
import logging
import os

from app.core.config import load_env_file
from psycopg.rows import dict_row

from app.pool import get_pool

logger = logging.getLogger(__name__)

# Seconds between refresh cycles.
DEFAULT_REFRESH_INTERVAL_SECONDS = 60 * 60  # 1 hour


def _default_marketplace() -> str:
    load_env_file()
    return os.environ.get("DEFAULT_MARKETPLACE", "UK")


async def cache_refresh_loop(interval_seconds: int = DEFAULT_REFRESH_INTERVAL_SECONDS) -> None:
    """Periodically refresh ``keyword_selection_candidates_monthly`` and
    ``keyword_compare_snapshot``.  Intended to be run as a standalone process,
    not inside the FastAPI worker.
    """
    await asyncio.sleep(30)

    while True:
        try:
            await asyncio.to_thread(_do_refresh)
        except Exception:
            logger.exception("Background cache refresh failed — will retry in %ss", interval_seconds)

        await asyncio.sleep(interval_seconds)


def _do_refresh() -> None:
    """Run both cache-table refreshes inside one explicit transaction."""
    from app.services.keyword_compare_snapshot import refresh_compare_snapshot
    from app.services.product_selection_cache import refresh_cache

    marketplace = _default_marketplace()
    pool = get_pool()
    with pool.connection() as conn:
        conn.row_factory = dict_row
        try:
            # Cache refreshes are heavier than normal API reads.  Give them a
            # bounded window, but do not let one blocked statement hold a pool
            # connection forever.
            conn.execute("SET LOCAL statement_timeout = '10min'")
            conn.execute("SET LOCAL lock_timeout = '5s'")

            n_ps = refresh_cache(conn, marketplace=marketplace)
            logger.info("product_selection_cache refreshed: %s rows", n_ps)

            n_cs = refresh_compare_snapshot(conn, marketplace=marketplace)
            logger.info("keyword_compare_snapshot refreshed: %s rows", n_cs)

            conn.commit()
        except Exception:
            conn.rollback()
            raise
