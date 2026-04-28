"""Wrapper around `yt-dlp` for metadata extraction (no download)."""
from __future__ import annotations

from typing import Any

from yt_dlp import YoutubeDL

from ..core.config import get_settings
from ..schemas.jobs import FormatInfo, MetadataResponse


def _classify(fmt: dict[str, Any]) -> str:
    has_v = fmt.get("vcodec") and fmt["vcodec"] != "none"
    has_a = fmt.get("acodec") and fmt["acodec"] != "none"
    if has_v and has_a:
        return "muxed"
    if has_v:
        return "video"
    if has_a:
        return "audio"
    return "muxed"


def fetch_metadata(url: str) -> MetadataResponse:
    settings = get_settings()
    opts: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
    }
    if settings.yt_dlp_cookies_path:
        opts["cookiefile"] = settings.yt_dlp_cookies_path
    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)

    formats: list[FormatInfo] = []
    for f in info.get("formats", []) or []:
        if f.get("format_note") == "storyboard":
            continue
        formats.append(
            FormatInfo(
                format_id=str(f.get("format_id", "")),
                ext=str(f.get("ext", "")),
                resolution=f.get("resolution") or (f"{f.get('height')}p" if f.get("height") else None),
                fps=f.get("fps"),
                vcodec=f.get("vcodec"),
                acodec=f.get("acodec"),
                filesize=f.get("filesize") or f.get("filesize_approx"),
                tbr=f.get("tbr"),
                abr=f.get("abr"),
                note=f.get("format_note"),
                kind=_classify(f),  # type: ignore[arg-type]
            )
        )

    return MetadataResponse(
        id=str(info.get("id", "")),
        title=str(info.get("title", "")),
        uploader=info.get("uploader") or info.get("channel"),
        duration=info.get("duration"),
        thumbnail=info.get("thumbnail"),
        webpage_url=str(info.get("webpage_url") or url),
        formats=formats,
    )
