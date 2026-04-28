"""RQ worker entrypoint with concurrency capped at MAX_CONCURRENT_JOBS.

Each worker process pulls one job at a time. To respect the 2-job concurrency
budget on a 2-core VPS, run two worker processes (the docker-compose service
uses `--scale worker=2` or sets `replicas: 2`).
"""
from __future__ import annotations

import logging

from rq import Worker

from app.core.config import get_settings
from app.core.queue import get_queue
from app.core.redis_client import get_redis_binary


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )
    settings = get_settings()
    settings.download_dir.mkdir(parents=True, exist_ok=True)
    # RQ requires a raw-bytes connection (decode_responses=False) since it
    # stores zlib-compressed pickle blobs; the decoded connection used
    # elsewhere in the app would UnicodeDecodeError on those.
    worker = Worker([get_queue()], connection=get_redis_binary())
    worker.work(with_scheduler=True)


if __name__ == "__main__":
    main()
