"""Download submission, status, and file-serving endpoints."""
from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse

from ..core.config import get_settings
from ..core.queue import active_job_count, get_queue
from ..core.rate_limit import check_and_increment, usage
from ..core.rate_limit import rollback as rollback_rate_limit
from ..schemas.jobs import (
    CapacityResponse,
    DownloadRequest,
    JobInfo,
    MetadataRequest,
    MetadataResponse,
)
from ..services import jobs as jobs_svc
from ..services.metadata import fetch_metadata
from .deps import get_current_user

router = APIRouter(tags=["downloads"])


@router.post("/metadata", response_model=MetadataResponse)
def metadata(req: MetadataRequest, user: str = Depends(get_current_user)) -> MetadataResponse:
    try:
        return fetch_metadata(str(req.url))
    except Exception as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, f"failed to fetch metadata: {exc}"
        ) from exc


@router.get("/capacity", response_model=CapacityResponse)
def capacity(user: str = Depends(get_current_user)) -> CapacityResponse:
    settings = get_settings()
    active = active_job_count()
    busy = active >= settings.max_concurrent_jobs
    return CapacityResponse(
        busy=busy,
        active_jobs=active,
        max_jobs=settings.max_concurrent_jobs,
        message="please wait for some time" if busy else None,
    )


@router.post("/downloads", response_model=JobInfo, status_code=status.HTTP_202_ACCEPTED)
def create_download(req: DownloadRequest, user: str = Depends(get_current_user)) -> JobInfo:
    settings = get_settings()

    # Capacity gate -> "please wait for some time"
    if active_job_count() >= settings.max_concurrent_jobs:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "please wait for some time"
        )

    allowed, used, limit, rl_member = check_and_increment(user)
    if not allowed:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"rate limit exceeded ({used}/{limit} per hour)",
        )

    job_id = uuid.uuid4().hex[:12]
    try:
        jobs_svc.init_job(job_id, user=user, mode=req.mode, url=str(req.url))
        queue = get_queue()
        queue.enqueue(
            "app.workers.runner.run_download",
            job_id,
            req.model_dump(mode="json"),
            job_id=job_id,
            result_ttl=3600,
            failure_ttl=3600,
        )
    except Exception as exc:
        # Roll back the rate-limit slot we just consumed so the user doesn't
        # permanently lose it on a transient infra error (e.g. RQ queue
        # serialization failure, Valkey hiccup).
        rollback_rate_limit(user, rl_member)
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, f"failed to enqueue job: {exc}"
        ) from exc

    info = jobs_svc.get_job(job_id)
    assert info is not None
    return info


@router.get("/downloads", response_model=list[JobInfo])
def list_downloads(user: str = Depends(get_current_user)) -> list[JobInfo]:
    return jobs_svc.list_user_jobs(user)


def _load_owned_job(job_id: str, user: str) -> JobInfo:
    """Load a job and ensure it belongs to the calling user.

    To avoid leaking the existence of jobs owned by other users, we return
    the same 404 whether the job is missing or simply not owned by the caller.
    """
    raw = jobs_svc.get_raw(job_id)
    info = jobs_svc.get_job(job_id)
    if not raw or not info or raw.get("user") != user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "job not found")
    return info


@router.get("/downloads/{job_id}", response_model=JobInfo)
def job_status(job_id: str, user: str = Depends(get_current_user)) -> JobInfo:
    return _load_owned_job(job_id, user)


@router.get("/downloads/{job_id}/file")
def download_file(job_id: str, user: str = Depends(get_current_user)) -> FileResponse:
    settings = get_settings()
    info = _load_owned_job(job_id, user)
    if info.status != "completed" or not info.filename:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "file not ready")
    path = Path(settings.download_dir) / info.filename
    if not path.exists():
        raise HTTPException(status.HTTP_410_GONE, "file expired")

    safe_title = (info.title or job_id).replace("/", "_")[:120]
    download_name = f"{safe_title}{path.suffix}"
    return FileResponse(path, filename=download_name, media_type="application/octet-stream")


@router.get("/usage")
def my_usage(user: str = Depends(get_current_user)) -> dict[str, int]:
    used, limit = usage(user)
    return {"used": used, "limit": limit}
