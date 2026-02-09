"""
db.__init__
• get_pool()  – lazy-creates a global asyncpg pool with retry logic
• pool        – module-level singleton you can import anywhere

Usage:
    from db import get_pool
    pool = await get_pool()
"""
from __future__ import annotations

import asyncio, asyncpg, logging
from asyncpg import exceptions as pg_exc
from config.config import settings            # ← NEW

log = logging.getLogger(__name__)

_RETRY_EXC = (ConnectionRefusedError, OSError, pg_exc.CannotConnectNowError)
_pool: asyncpg.Pool | None = None             # module-level cache


async def _create_pool(retries: int = 10, delay: int = 2) -> asyncpg.Pool:
    for attempt in range(1, retries + 1):
        try:
            log.info("DB: connecting %s", settings.DATABASE_URL)
            return await asyncpg.create_pool(
                settings.DATABASE_URL,
                min_size=1,
                max_size=5,
            )
        except _RETRY_EXC as e:
            if attempt == retries:
                raise
            log.warning("[DB] retry %s/%s – %s; sleep %ss",
                        attempt, retries, e, delay)
            await asyncio.sleep(delay)


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await _create_pool()
    return _pool