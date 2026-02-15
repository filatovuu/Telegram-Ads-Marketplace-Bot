"""Redis-based idempotency key guard."""

import logging

import redis.asyncio as aioredis

from app.core.config import settings

logger = logging.getLogger(__name__)

_redis: aioredis.Redis | None = None


async def _get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    return _redis


async def check_idempotency(key: str, ttl: int = 300) -> bool:
    """Return True if this is the first call with this key (proceed).

    Return False if a duplicate (skip).
    """
    try:
        r = await _get_redis()
        was_set = await r.set(f"idempotent:{key}", "1", nx=True, ex=ttl)
        return bool(was_set)
    except Exception:
        logger.exception("Idempotency check failed for key=%s, allowing through", key)
        return True
