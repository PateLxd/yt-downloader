"""Job state persistence in Valkey.

We avoid relying solely on RQ's status because we need richer progress data
(percent, speed, eta, filename) and we want it accessible even after the RQ
job result is cleared.
"""
from __future__ import annotations

import json
import time
from typing import Any

from ..core.config import get_settings
from ..core.redis_client import get_redis
from ..schemas.jobs import JobInfo

_USER_INDEX = "ytdl:jobs:user:"  # + username -> sorted set of job_ids by created_at
_JOB_TTL = 60 * 60 * 24  # keep job metadata for 1 day


def _job_key(job_id: str) -> str:
    return f"{get_settings().progress_key_prefix}{job_id}"


def init_job(job_id: str, user: str, mode: str, url: str) -> None:
    r = get_redis()
    now = time.time()
    payload = {
        "id": job_id,
        "status": "queued",
        "progress": 0.0,
        "mode": mode,
        "url": url,
        "user": user,
        "created_at": now,
    }
    r.set(_job_key(job_id), json.dumps(payload), ex=_JOB_TTL)
    r.zadd(f"{_USER_INDEX}{user}", {job_id: now})
    r.expire(f"{_USER_INDEX}{user}", _JOB_TTL)


def update_job(job_id: str, **fields: Any) -> None:
    """Merge ``fields`` into the stored job record.

    Explicit ``None`` values are preserved so callers can clear stale data
    (e.g. wiping ``speed``/``eta`` once a job is complete). Use ``**fields``
    to only update specific keys — keys you do not pass are left untouched.
    """
    r = get_redis()
    raw = r.get(_job_key(job_id))
    data = json.loads(raw) if raw else {"id": job_id}
    data.update(fields)
    r.set(_job_key(job_id), json.dumps(data), ex=_JOB_TTL)


def get_job(job_id: str) -> JobInfo | None:
    r = get_redis()
    raw = r.get(_job_key(job_id))
    if not raw:
        return None
    data = json.loads(raw)
    return JobInfo(
        id=data.get("id", job_id),
        status=data.get("status", "queued"),
        progress=float(data.get("progress", 0.0)),
        speed=data.get("speed"),
        eta=data.get("eta"),
        title=data.get("title"),
        filename=data.get("filename"),
        size_bytes=data.get("size_bytes"),
        error=data.get("error"),
        error_code=data.get("error_code"),
        mode=data.get("mode"),
        created_at=data.get("created_at"),
        finished_at=data.get("finished_at"),
    )


def get_raw(job_id: str) -> dict[str, Any] | None:
    raw = get_redis().get(_job_key(job_id))
    return json.loads(raw) if raw else None


def list_user_jobs(user: str, limit: int = 25) -> list[JobInfo]:
    r = get_redis()
    ids = r.zrevrange(f"{_USER_INDEX}{user}", 0, limit - 1)
    out: list[JobInfo] = []
    for jid in ids:
        info = get_job(jid)
        if info:
            out.append(info)
    return out
