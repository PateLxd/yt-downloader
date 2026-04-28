"""Sliding-window rate limiter backed by Valkey.

The check + increment must run atomically to avoid TOCTOU races where two
concurrent requests both see ``used < limit`` and both pass through. We use
a Lua script (``EVAL``) so the trim/count/zadd happens inside a single Redis
operation.
"""
from __future__ import annotations

import time

from .config import get_settings
from .redis_client import get_redis

# KEYS[1] = sorted-set key
# ARGV[1] = window_start (epoch seconds, exclusive lower bound to keep)
# ARGV[2] = limit
# ARGV[3] = score (now)
# ARGV[4] = member (unique tag for this request)
# ARGV[5] = expiry seconds
# Returns: { allowed (0|1), used_after }
_LUA = """
redis.call('ZREMRANGEBYSCORE', KEYS[1], 0, ARGV[1])
local used = redis.call('ZCARD', KEYS[1])
if tonumber(used) >= tonumber(ARGV[2]) then
  return {0, used}
end
redis.call('ZADD', KEYS[1], ARGV[3], ARGV[4])
redis.call('EXPIRE', KEYS[1], ARGV[5])
return {1, used + 1}
"""


def _key(user: str) -> str:
    return f"ytdl:ratelimit:{user}"


def check_and_increment(user: str) -> tuple[bool, int, int]:
    """Returns (allowed, used, limit).

    ``used`` reflects the count *after* the (possible) increment when allowed,
    or the current count when denied.
    """
    settings = get_settings()
    limit = settings.rate_limit_per_hour
    now = time.time()
    window_start = now - 3600
    r = get_redis()
    member = f"{now}-{int(now * 1000) % 100000}"
    script = r.register_script(_LUA)
    allowed_raw, used_raw = script(
        keys=[_key(user)],
        args=[window_start, limit, now, member, 3600 + 60],
    )
    return bool(int(allowed_raw)), int(used_raw), limit


def usage(user: str) -> tuple[int, int]:
    settings = get_settings()
    r = get_redis()
    key = _key(user)
    r.zremrangebyscore(key, 0, time.time() - 3600)
    return r.zcard(key), settings.rate_limit_per_hour
