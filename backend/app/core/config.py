"""Runtime configuration for the backend."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "yt-downloader"
    debug: bool = False

    # Auth
    jwt_secret: str = Field(default="change-me-in-prod", min_length=8)
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24  # 1 day
    # Comma-separated `username:password` pairs. Passwords may be plaintext or bcrypt hashes.
    auth_users: str = "admin:admin"

    # Storage
    download_dir: Path = Path("/tmp/downloads")
    file_ttl_seconds: int = 600  # 10 minutes

    # Queue / Valkey
    redis_url: str = "redis://valkey:6379/0"
    queue_name: str = "downloads"
    max_concurrent_jobs: int = 2
    progress_key_prefix: str = "ytdl:progress:"

    # Limits
    rate_limit_per_hour: int = 5
    max_video_seconds: int = 2 * 60 * 60  # 2 hours

    # yt-dlp
    # Path to a Netscape-format cookies file. Lets yt-dlp pass YouTube's
    # "Sign in to confirm you're not a bot" challenge (and similar) on hosts
    # whose IPs Google flags. Leave empty to disable.
    yt_dlp_cookies_path: str = ""

    # TTL for the runtime cookies override pasted through the UI. The file-
    # on-disk cookies path above is long-lived; this one is a short-lived
    # safety valve so a user can unstick a stale-cookie situation from the
    # browser without SSHing into the box. Defaults to 7 days.
    cookies_override_ttl_seconds: int = 7 * 24 * 60 * 60

    # CORS
    cors_origins: str = "*"


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    s.download_dir.mkdir(parents=True, exist_ok=True)
    return s
