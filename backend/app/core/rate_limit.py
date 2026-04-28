"""Sliding-window rate limiter backed by Valkey."""
from __future__ import annotations

import time

from .config import get_settings
from .redis_client import get_redis


def _key(user: str) -> str:
    return f"ytdl:ratelimit:{user}"


def check_and_increment(user: str) -> tuple[bool, int, int]:
    """Returns (allowed, used, limit). Rolling 1-hour window via sorted-set."""
    settings = get_settings()
    limit = settings.rate_limit_per_hour
    now = time.time()
    window_start = now - 3600
    r = get_redis()
    key = _key(user)

    pipe = r.pipeline()
    pipe.zremrangebyscore(key, 0, window_start)
    pipe.zcard(key)
    _, used = pipe.execute()

    if used >= limit:
        return False, used, limit

    pipe = r.pipeline()
    pipe.zadd(key, {f"{now}-{int(now * 1000) % 100000}": now})
    pipe.expire(key, 3600 + 60)
    pipe.execute()
    return True, used + 1, limit


def usage(user: str) -> tuple[int, int]:
    settings = get_settings()
    r = get_redis()
    key = _key(user)
    r.zremrangebyscore(key, 0, time.time() - 3600)
    return r.zcard(key), settings.rate_limit_per_hour
