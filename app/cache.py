import json
from typing import Any, Optional

import redis.asyncio as aioredis
from settings import settings

_redis: Optional[aioredis.Redis] = None


async def init_redis() -> None:
    global _redis
    _redis = aioredis.from_url(settings.redis_url, decode_responses=True)


async def close_redis() -> None:
    if _redis:
        await _redis.aclose()


async def cache_get(key: str):
    if _redis is None:
        return None
    value = await _redis.get(key)
    return json.loads(value) if value else None


async def cache_set(key: str, value: Any, ttl: int = 300) -> None:
    if _redis is None:
        return
    await _redis.setex(key, ttl, json.dumps(value, default=str))


async def cache_delete_pattern(pattern: str) -> None:
    if _redis is None:
        return
    keys = await _redis.keys(pattern)
    if keys:
        await _redis.delete(*keys)
