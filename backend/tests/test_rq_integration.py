"""Verify RQ works end-to-end against a live Valkey.

This guards against regressions like passing a ``decode_responses=True``
connection to RQ (which would UnicodeDecodeError on the zlib-compressed pickle
blobs RQ stores in Redis hashes).

Skipped when Valkey isn't reachable.
"""
from __future__ import annotations

import os

import pytest
import redis
from rq import SimpleWorker

REDIS_URL = os.environ.setdefault("REDIS_URL", "redis://localhost:6399/0")


def _ping() -> bool:
    try:
        redis.Redis.from_url(REDIS_URL, socket_timeout=0.5).ping()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _ping(), reason="Valkey not reachable")


def _payload_job(payload):
    """Top-level callable required so pickle can resolve it on the worker."""
    return {"echo": payload, "len": len(payload)}


@pytest.fixture(autouse=True)
def _flush():
    redis.Redis.from_url(REDIS_URL).flushdb()
    yield
    redis.Redis.from_url(REDIS_URL).flushdb()


def test_rq_can_round_trip_a_job_with_our_connection():
    from app.core.queue import get_queue
    from app.core.redis_client import get_redis_binary

    # Heavy-ish payload to force zlib's binary blob through Redis.
    payload = "x" * 5000
    queue = get_queue()
    job = queue.enqueue(_payload_job, payload)

    worker = SimpleWorker([queue], connection=get_redis_binary())
    worker.work(burst=True)

    job.refresh()
    assert job.is_finished, f"job ended in status={job.get_status()} err={job.exc_info}"
    assert job.result == {"echo": payload, "len": len(payload)}
