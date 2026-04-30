"""Wrapper around `yt-dlp` for metadata extraction (no download)."""
from __future__ import annotations

from typing import Any

from yt_dlp import YoutubeDL

from ..schemas.jobs import FormatInfo, MetadataResponse
from .cookies import (
    apply_cookies_to_opts,
    apply_pot_provider_to_opts,
    apply_proxy_to_opts,
    cleanup_tmp_cookies,
)


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
    opts: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
        # Disable format selection during metadata extraction. We don't
        # need yt-dlp to pick a format here — we just want the full list
        # of formats to show the user in the UI. Leaving this at the
        # default (``bestvideo*+bestaudio/best``) means yt-dlp will raise
        # ``ExtractorError: Requested format is not available`` whenever
        # the current player client returns SABR-only / stub / DRM'd
        # formats that the default selector can't combine — which is
        # common on flagged datacenter IPs and actually what prompted
        # this whole PO-token saga. Using ``all`` guarantees selection
        # succeeds as long as at least one format was extracted.
        "format": "all",
    }
    tmp_cookies = apply_cookies_to_opts(opts)
    apply_pot_provider_to_opts(opts)
    apply_proxy_to_opts(opts)
    try:
        with YoutubeDL(opts) as ydl:
            # ``process=False`` skips yt-dlp's post-extraction processing
            # (format selection, URL signing, etc.) and returns the raw
            # info dict straight from the extractor. Combined with
            # ``format=all`` above, this makes the metadata call robust
            # against format-selector edge cases we don't care about
            # here — we just need id/title/duration/thumbnail and the
            # raw formats list for the UI picker. The download worker
            # (``app.workers.runner``) still runs with full processing
            # so the actual format selection happens there.
            info = ydl.extract_info(url, download=False, process=False)
    finally:
        cleanup_tmp_cookies(tmp_cookies)

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
