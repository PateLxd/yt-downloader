"""Integration tests against a live Valkey instance.

Skipped automatically if no Valkey is reachable at ``REDIS_URL`` / the default
test port. Run a Valkey container first:

    docker run -d --rm -p 6399:6379 valkey/valkey:8-alpine

then ``REDIS_URL=redis://localhost:6399/0 pytest``.
"""
from __future__ import annotations

import os
import uuid

import pytest
import redis

REDIS_URL = os.environ.setdefault("REDIS_URL", "redis://localhost:6399/0")


def _ping() -> bool:
    try:
        redis.Redis.from_url(REDIS_URL, socket_timeout=0.5).ping()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _ping(), reason="Valkey not reachable")


@pytest.fixture(autouse=True)
def _isolate_keys():
    r = redis.Redis.from_url(REDIS_URL, decode_responses=True)
    r.flushdb()
    yield
    r.flushdb()


def test_rate_limit_blocks_after_limit():
    from app.core import rate_limit
    from app.core.config import get_settings

    get_settings.cache_clear()  # type: ignore[attr-defined]
    user = f"u-{uuid.uuid4().hex[:6]}"

    limit = get_settings().rate_limit_per_hour
    used_seq: list[int] = []
    for _ in range(limit + 2):
        allowed, used, _ = rate_limit.check_and_increment(user)
        used_seq.append((1 if allowed else 0, used))  # type: ignore[arg-type]

    allowed_count = sum(1 for a, _ in used_seq if a == 1)
    assert allowed_count == limit
    # Once at limit, denials report the current count (== limit), not limit+1.
    last_allowed_used, last_denied_used = None, None
    for a, used in used_seq:
        if a == 1:
            last_allowed_used = used
        else:
            last_denied_used = used
    assert last_allowed_used == limit
    assert last_denied_used == limit


def test_update_job_preserves_explicit_none():
    from app.services import jobs

    job_id = uuid.uuid4().hex[:8]
    jobs.init_job(job_id, user="alice", mode="video", url="https://example.com")
    jobs.update_job(job_id, speed="1.2MiB/s", eta="00:30")
    info = jobs.get_job(job_id)
    assert info is not None
    assert info.speed == "1.2MiB/s"
    assert info.eta == "00:30"

    jobs.update_job(job_id, status="completed", speed=None, eta=None)
    info = jobs.get_job(job_id)
    assert info is not None
    assert info.status == "completed"
    assert info.speed is None
    assert info.eta is None


def test_get_raw_exposes_owner_for_authz():
    from app.services import jobs

    job_id = uuid.uuid4().hex[:8]
    jobs.init_job(job_id, user="alice", mode="audio", url="https://example.com")
    raw = jobs.get_raw(job_id)
    assert raw is not None
    assert raw["user"] == "alice"


def test_idor_protection_via_endpoint(monkeypatch):
    """Authenticated user 'eve' cannot read 'alice' job_id."""
    from fastapi.testclient import TestClient

    monkeypatch.setenv("AUTH_USERS", "alice:wonder,eve:evil")
    monkeypatch.setenv("JWT_SECRET", "test-secret-for-idor")

    # Reset cached settings + redis so the new env is honoured.
    from app.core.config import get_settings
    from app.core.queue import get_queue
    from app.core.redis_client import get_redis

    get_settings.cache_clear()  # type: ignore[attr-defined]
    get_redis.cache_clear()  # type: ignore[attr-defined]
    get_queue.cache_clear()  # type: ignore[attr-defined]

    from app.main import create_app
    from app.services import jobs

    job_id = uuid.uuid4().hex[:8]
    jobs.init_job(job_id, user="alice", mode="video", url="https://example.com")
    jobs.update_job(job_id, status="completed", filename=f"{job_id}.mp4", title="t")

    app = create_app()
    client = TestClient(app)

    eve_token = client.post(
        "/api/auth/login", json={"username": "eve", "password": "evil"}
    ).json()["access_token"]
    res = client.get(
        f"/api/downloads/{job_id}", headers={"Authorization": f"Bearer {eve_token}"}
    )
    assert res.status_code == 404
