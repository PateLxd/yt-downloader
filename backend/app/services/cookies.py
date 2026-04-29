"""Runtime cookies override.

Lets an authenticated user paste a fresh Netscape-format cookies.txt into
the UI when yt-dlp hits YouTube's bot challenge. The cookies are stored in
Valkey with a TTL so both the backend (metadata) and the worker
(download) see the same value without needing a container restart or a
new file on disk.

Shape of the value in Valkey: the raw cookies.txt content as a string.
Key: ``ytdl:cookies:override`` (global — this is a single-tenant style
app, all authenticated users share the cookie pool, just like the
on-disk ``secrets/cookies.txt`` file).
"""
from __future__ import annotations

import logging
import os
import tempfile
from typing import Any

from ..core.config import get_settings
from ..core.redis_client import get_redis

log = logging.getLogger(__name__)

_KEY = "ytdl:cookies:override"


def save_override(content: str, ttl_seconds: int) -> None:
    """Persist a cookies.txt blob for ``ttl_seconds``. Overwrites any existing override."""
    get_redis().set(_KEY, content, ex=ttl_seconds)


def get_override() -> str | None:
    """Fetch the current override from Redis.

    Returns ``None`` if there's no override *or* Redis is unreachable.
    Treating a Redis outage as "no override" is the right fallback: the
    runner will then use the on-disk cookies path if configured, instead
    of exploding the whole download pipeline on a transient cache hiccup.
    """
    try:
        value = get_redis().get(_KEY)
    except Exception as exc:
        log.warning("cookies override lookup failed (%s); falling back to file", exc)
        return None
    if value is None:
        return None
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def clear_override() -> None:
    get_redis().delete(_KEY)


def override_ttl() -> int:
    """Remaining TTL of the override cookies in seconds (-1 if none / no expiry)."""
    try:
        ttl = get_redis().ttl(_KEY)
    except Exception:
        return -1
    try:
        return int(ttl)
    except (TypeError, ValueError):
        return -1


def apply_cookies_to_opts(opts: dict[str, Any]) -> str | None:
    """Resolve which cookies file (if any) yt-dlp should use and set it on ``opts``.

    Precedence:
    1. Live override from Redis (most recent — user-pasted).
    2. ``YT_DLP_COOKIES_PATH`` from settings (on-disk file, persisted across deploys).
    3. No cookies.

    When the override is used we materialize it to a tmp file because yt-dlp
    only accepts a path for ``cookiefile`` — not inline bytes. Returns the
    tmp file path so the caller can clean it up after yt-dlp has run.
    """
    override = get_override()
    if override:
        fd, tmp_path = tempfile.mkstemp(prefix="ytdl-cookies-", suffix=".txt")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(override)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
        opts["cookiefile"] = tmp_path
        return tmp_path

    settings = get_settings()
    if settings.yt_dlp_cookies_path:
        opts["cookiefile"] = settings.yt_dlp_cookies_path
    return None


def cleanup_tmp_cookies(tmp_path: str | None) -> None:
    if not tmp_path:
        return
    try:
        os.unlink(tmp_path)
    except OSError:
        pass


# Phrases yt-dlp emits when Google's bot challenge (or any equivalent
# cookie-required error) fires. Matched case-insensitively against
# ``str(exc)``. Keep this list tight to avoid false positives that would
# cause the frontend to pop the "paste cookies" modal on unrelated errors.
_BOT_CHALLENGE_MARKERS = (
    "sign in to confirm you",  # "Sign in to confirm you're not a bot"
    "use --cookies-from-browser",
    "use --cookies",
    "cookies are required",
    "confirm your age",  # age-gated videos need cookies too
    "this video is only available for registered users",
)


def is_bot_challenge_error(exc: BaseException) -> bool:
    msg = str(exc).lower()
    return any(marker in msg for marker in _BOT_CHALLENGE_MARKERS)
