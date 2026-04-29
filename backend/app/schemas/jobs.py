"""Pydantic schemas for the API."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, HttpUrl


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MetadataRequest(BaseModel):
    url: HttpUrl


class FormatInfo(BaseModel):
    format_id: str
    ext: str
    resolution: str | None = None
    fps: float | None = None
    vcodec: str | None = None
    acodec: str | None = None
    filesize: int | None = None
    tbr: float | None = None
    abr: float | None = None
    note: str | None = None
    kind: Literal["video", "audio", "muxed"] = "muxed"


class MetadataResponse(BaseModel):
    id: str
    title: str
    uploader: str | None = None
    duration: int | None = None
    thumbnail: str | None = None
    webpage_url: str
    formats: list[FormatInfo]


JobMode = Literal["video", "audio", "clip"]
VideoPreset = Literal["best", "balanced", "saver", "custom"]


class DownloadRequest(BaseModel):
    url: HttpUrl
    mode: JobMode = "video"
    # Video
    preset: VideoPreset | None = "balanced"
    max_height: int | None = Field(default=None, ge=144, le=4320)
    container: Literal["mp4", "mkv", "webm"] = "mp4"
    # Explicit yt-dlp format_id (overrides `preset`/`max_height` when set).
    # The backend wraps it as `{format_id}+bestaudio/{format_id}` so video-only
    # formats get muxed with the best audio track automatically.
    format_id: str | None = None
    # Audio
    audio_bitrate: Literal["64", "128", "192", "320"] | None = "192"
    # Clip
    start: str | None = None  # HH:MM:SS or seconds
    end: str | None = None


class JobInfo(BaseModel):
    id: str
    status: Literal["queued", "downloading", "completed", "failed"]
    progress: float = 0.0
    speed: str | None = None
    eta: str | None = None
    title: str | None = None
    filename: str | None = None
    size_bytes: int | None = None
    error: str | None = None
    # Structured error tag so the frontend can handle specific failure
    # modes (e.g. "cookies_required" → pop the paste-cookies modal)
    # without string-matching the free-form `error` text.
    error_code: str | None = None
    mode: JobMode | None = None
    created_at: float | None = None
    finished_at: float | None = None


class CapacityResponse(BaseModel):
    busy: bool
    active_jobs: int
    max_jobs: int
    message: str | None = None
