"""Redis/Valkey connection helpers.

Two distinct connections are exposed:

* :func:`get_redis` returns a connection with ``decode_responses=True``. The
  application uses it for its own keys (rate-limit sorted sets, job-status
  JSON) where we want ``str`` results.
* :func:`get_redis_binary` returns a connection with ``decode_responses=False``.
  RQ stores zlib-compressed pickle blobs in Redis hashes; if RQ reads these
  through a decoded connection, redis-py raises ``UnicodeDecodeError`` before
  RQ even reaches its ``zlib.decompress`` call. RQ's queue and worker MUST use
  the binary connection.
"""
from __future__ import annotations

from functools import lru_cache

import redis

from .config import get_settings


@lru_cache
def get_redis() -> redis.Redis:
    """Decoded connection used for the application's own keys."""
    return redis.Redis.from_url(
        get_settings().redis_url, decode_responses=True, socket_timeout=5.0
    )


@lru_cache
def get_redis_binary() -> redis.Redis:
    """Raw-bytes connection — required by RQ for queue + worker."""
    return redis.Redis.from_url(
        get_settings().redis_url, decode_responses=False, socket_timeout=5.0
    )
