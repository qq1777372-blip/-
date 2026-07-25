from __future__ import annotations

import json
import time
from functools import lru_cache
from typing import Any

from redis import Redis
from redis.exceptions import RedisError

from .config import settings


REDIS_RETRY_COOLDOWN_SECONDS = 60
_redis_retry_after = 0.0


def _cache_key(key: str) -> str:
    return f"{settings.redis_prefix}:{key}"


@lru_cache(maxsize=1)
def get_redis_client() -> Redis | None:
    if not settings.redis_enabled:
        return None

    return Redis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_connect_timeout=0.2,
        socket_timeout=0.2,
        retry_on_timeout=False,
    )


def _redis_temporarily_disabled() -> bool:
    return time.monotonic() < _redis_retry_after


def _mark_redis_unavailable() -> None:
    global _redis_retry_after
    _redis_retry_after = time.monotonic() + REDIS_RETRY_COOLDOWN_SECONDS


def cache_get_json(key: str) -> Any | None:
    if _redis_temporarily_disabled():
        return None

    client = get_redis_client()
    if client is None:
        return None

    try:
        raw_value = client.get(_cache_key(key))
    except RedisError:
        _mark_redis_unavailable()
        return None

    if not raw_value:
        return None

    try:
        return json.loads(raw_value)
    except json.JSONDecodeError:
        return None


def cache_set_json(key: str, value: Any, ttl_seconds: int = 60) -> None:
    if _redis_temporarily_disabled():
        return

    client = get_redis_client()
    if client is None:
        return

    try:
        client.setex(
            _cache_key(key),
            ttl_seconds,
            json.dumps(value, ensure_ascii=False, default=str),
        )
    except RedisError:
        _mark_redis_unavailable()
        return
