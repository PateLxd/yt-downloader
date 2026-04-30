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


# yt-dlp YouTube player_clients that actually return downloadable formats
# when combined with a POT. The yt-dlp PO Token Guide's TL;DR is
# "Use a PO Token Provider plugin to provide the mweb client with a PO
# Token for GVS requests." (https://github.com/yt-dlp/yt-dlp/wiki/PO-Token-Guide)
#
# The earlier default here (web,web_safari,tv) is broken as of 2026-01:
# see backend/app/core/config.py for the full history. This list is
# the config-file default; operators can override via YT_DLP_PLAYER_CLIENTS.
_DEFAULT_POT_PLAYER_CLIENTS = ("mweb", "tv_simply")


def apply_pot_provider_to_opts(opts: dict[str, Any]) -> None:
    """Wire the bgutil POT provider's ``base_url`` into yt-dlp ``extractor_args``.

    The ``bgutil-ytdlp-pot-provider`` plugin auto-registers when the package
    is installed, but it only knows to look at ``http://127.0.0.1:4416`` by
    default. In our docker-compose setup the provider runs in its own
    container (service name ``pot-provider``), so we have to tell the
    plugin where to find it via the ``youtubepot-bgutilhttp:base_url``
    extractor arg.

    We also force ``player_client`` to ``mweb,tv_simply`` (yt-dlp's
    current recommended setup for POT) — see ``_DEFAULT_POT_PLAYER_CLIENTS``
    above for why. Operators can override the list via the
    ``YT_DLP_PLAYER_CLIENTS`` env var (comma-separated). Setting it to
    an empty string keeps yt-dlp's default rotation, in case a future
    yt-dlp update changes which clients consume POTs.

    Empty/unset settings.pot_provider_url is treated as "POT provider
    disabled": we don't inject extractor_args and yt-dlp behaves exactly
    as it did before this change. This matters for users who don't run
    the optional ``pot-provider`` Compose profile.

    Important: yt-dlp's extractor_args expects each value to be a list
    of strings, not a single string. Passing a bare string silently
    no-ops in some plugin versions.
    """
    settings = get_settings()
    base_url = (settings.pot_provider_url or "").strip()
    if not base_url:
        return

    existing = opts.get("extractor_args") or {}
    bgutil = dict(existing.get("youtubepot-bgutilhttp", {}))
    bgutil["base_url"] = [base_url]
    existing["youtubepot-bgutilhttp"] = bgutil

    # Player client pinning. ``yt_dlp_player_clients`` is comma-separated.
    # Setting it to whitespace/empty string is treated as "let yt-dlp
    # pick its own default rotation" (escape hatch in case a future
    # yt-dlp update broadens the POT-consuming client list).
    clients = [c.strip() for c in settings.yt_dlp_player_clients.split(",") if c.strip()]
    if clients:
        youtube = dict(existing.get("youtube", {}))
        # Don't clobber a player_client value the caller already set.
        if "player_client" not in youtube:
            youtube["player_client"] = clients
            existing["youtube"] = youtube

    opts["extractor_args"] = existing


def apply_proxy_to_opts(opts: dict[str, Any]) -> None:
    """Set the yt-dlp ``proxy`` option from settings, if configured.

    Mirrors yt-dlp's CLI ``--proxy`` flag. Supports HTTP/HTTPS/SOCKS5.
    Leaves ``opts`` untouched when the setting is empty so behavior on
    hosts that don't need a proxy is identical to before this change.
    """
    proxy = (get_settings().yt_dlp_proxy or "").strip()
    if proxy:
        opts["proxy"] = proxy


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
