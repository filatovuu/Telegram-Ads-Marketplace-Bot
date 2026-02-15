"""Redis caching utility."""

import json
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


def make_cache_key(*parts: str) -> str:
    return "cache:" + ":".join(parts)


async def cache_get(key: str) -> str | None:
    try:
        r = await _get_redis()
        return await r.get(key)
    except Exception:
        logger.exception("Cache get failed for key=%s", key)
        return None


async def cache_set(key: str, value: str, ttl: int = 60) -> None:
    try:
        r = await _get_redis()
        await r.set(key, value, ex=ttl)
    except Exception:
        logger.exception("Cache set failed for key=%s", key)


async def cache_delete_pattern(pattern: str) -> None:
    """Delete all keys matching a pattern."""
    try:
        r = await _get_redis()
        cursor = 0
        while True:
            cursor, keys = await r.scan(cursor, match=pattern, count=100)
            if keys:
                await r.delete(*keys)
            if cursor == 0:
                break
    except Exception:
        logger.exception("Cache delete pattern failed for pattern=%s", pattern)
