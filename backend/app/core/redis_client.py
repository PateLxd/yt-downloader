"""Redis/Valkey connection helpers."""
from __future__ import annotations

from functools import lru_cache

import redis

from .config import get_settings


@lru_cache
def get_redis() -> redis.Redis:
    return redis.Redis.from_url(
        get_settings().redis_url, decode_responses=True, socket_timeout=5.0
    )
