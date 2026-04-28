"""Background sweeper that deletes downloaded files older than the TTL."""
from __future__ import annotations

import logging
import threading
import time
from pathlib import Path

from ..core.config import get_settings

log = logging.getLogger(__name__)

_thread: threading.Thread | None = None
_stop = threading.Event()


def _sweep_once() -> int:
    settings = get_settings()
    ttl = settings.file_ttl_seconds
    cutoff = time.time() - ttl
    removed = 0
    for path in Path(settings.download_dir).glob("*"):
        try:
            if path.is_file() and path.stat().st_mtime < cutoff:
                path.unlink(missing_ok=True)
                removed += 1
        except OSError as exc:
            log.warning("cleanup failed for %s: %s", path, exc)
    if removed:
        log.info("cleanup removed %d files", removed)
    return removed


def _loop() -> None:
    while not _stop.is_set():
        try:
            _sweep_once()
        except Exception:
            log.exception("cleanup loop error")
        # Sweep every 60s; cron handles it too in production.
        _stop.wait(60.0)


def start_cleanup_thread() -> None:
    global _thread
    if _thread and _thread.is_alive():
        return
    _stop.clear()
    _thread = threading.Thread(target=_loop, name="ytdl-cleanup", daemon=True)
    _thread.start()


def stop_cleanup_thread() -> None:
    _stop.set()
