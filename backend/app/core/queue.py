"""RQ queue plumbing on top of Valkey."""
from __future__ import annotations

from functools import lru_cache

from rq import Queue

from .config import get_settings
from .redis_client import get_redis_binary


@lru_cache
def get_queue() -> Queue:
    # RQ stores zlib-compressed pickle blobs; it needs the raw-bytes connection.
    return Queue(
        name=get_settings().queue_name,
        connection=get_redis_binary(),
        default_timeout=60 * 60 * 3,  # 3h hard cap per job
    )


def active_job_count() -> int:
    """Number of queued + in-progress jobs in our queue."""
    q = get_queue()
    return q.count + q.started_job_registry.count
