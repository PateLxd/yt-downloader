"""Job runner executed by RQ workers.

Wraps yt-dlp with a progress hook that writes percent/speed/eta into Valkey
so the API layer can serve real-time progress to the frontend via polling.
"""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

from yt_dlp import YoutubeDL

from ..core.config import get_settings
from ..services.cookies import (
    apply_cookies_to_opts,
    cleanup_tmp_cookies,
    is_bot_challenge_error,
)
from ..services.jobs import update_job

log = logging.getLogger(__name__)


def _format_for_video(
    preset: str | None,
    max_height: int | None,
    container: str,
    format_id: str | None = None,
) -> str:
    # Explicit format selection from the UI's "All formats" picker. Wrap with
    # +bestaudio so video-only formats (e.g. DASH 1080p) get muxed; the
    # `/{format_id}` fallback handles muxed/audio-only formats that already
    # contain audio.
    if format_id:
        return f"{format_id}+bestaudio/{format_id}"

    height_cap: int | None
    if preset == "best":
        height_cap = 2160
    elif preset == "balanced":
        height_cap = 1080
    elif preset == "saver":
        height_cap = 480
    elif preset == "custom":
        height_cap = max_height
    else:
        height_cap = max_height or 1080

    cap = f"[height<=?{height_cap}]" if height_cap else ""
    if container == "mp4":
        return f"bestvideo{cap}[ext=mp4]+bestaudio[ext=m4a]/bestvideo{cap}+bestaudio/best{cap}"
    return f"bestvideo{cap}+bestaudio/best{cap}"


def _hook(job_id: str):
    last_write = [0.0]

    def hook(d: dict[str, Any]) -> None:
        status = d.get("status")
        now = time.time()
        if status == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            done = d.get("downloaded_bytes") or 0
            percent = (done / total * 100.0) if total else 0.0
            # Throttle writes to avoid hammering Valkey.
            if now - last_write[0] >= 0.5 or percent >= 99.5:
                update_job(
                    job_id,
                    status="downloading",
                    progress=round(percent, 1),
                    speed=d.get("_speed_str"),
                    eta=d.get("_eta_str"),
                )
                last_write[0] = now
        elif status == "finished":
            update_job(job_id, progress=99.0, status="downloading")
        elif status == "error":
            update_job(job_id, status="failed", error="yt-dlp reported error")

    return hook


def _build_ydl_opts(job_id: str, req: dict[str, Any], outtmpl: str) -> tuple[dict[str, Any], str | None]:
    settings = get_settings()
    mode = req["mode"]
    opts: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "outtmpl": outtmpl,
        "progress_hooks": [_hook(job_id)],
        "concurrent_fragment_downloads": 2,
        "retries": 5,
        "fragment_retries": 5,
    }
    tmp_cookies = apply_cookies_to_opts(opts)

    if mode == "audio":
        bitrate = req.get("audio_bitrate") or "192"
        opts.update(
            {
                "format": "bestaudio/best",
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": str(bitrate),
                    }
                ],
                "final_ext": "mp3",
            }
        )
    elif mode == "clip":
        start = req.get("start") or "0:00:00"
        end = req.get("end")
        section = f"*{start}-{end}" if end else f"*{start}-inf"
        opts.update(
            {
                "format": _format_for_video(
                    req.get("preset"),
                    req.get("max_height"),
                    req.get("container", "mp4"),
                    req.get("format_id"),
                ),
                "merge_output_format": req.get("container", "mp4"),
                "download_ranges": _section_ranges(section),
                # Stream-copy the clip instead of re-encoding at exact
                # keyframes. force_keyframes_at_cuts=True would re-encode the
                # whole segment with ffmpeg, which on a 2-core VPS can take
                # many minutes and appears as a stuck job to the user. Trade-
                # off: start/end may land a few seconds early (at the nearest
                # upstream keyframe), which is acceptable for human-picked
                # ranges and fast enough to feel instant.
                "force_keyframes_at_cuts": False,
            }
        )
    else:  # video
        opts.update(
            {
                "format": _format_for_video(
                    req.get("preset"),
                    req.get("max_height"),
                    req.get("container", "mp4"),
                    req.get("format_id"),
                ),
                "merge_output_format": req.get("container", "mp4"),
            }
        )

    # Hard cap duration based on settings.max_video_seconds.
    # Skip in clip mode: the user is asking for a slice, so the source's full
    # duration is irrelevant — match_filter would otherwise reject e.g. a
    # 30-second clip taken from a 3-hour livestream.
    if mode != "clip":
        opts["match_filter"] = _max_duration_filter(settings.max_video_seconds)
    return opts, tmp_cookies


def _max_duration_filter(max_seconds: int):
    def _filter(info: dict[str, Any], *, incomplete: bool = False) -> str | None:
        dur = info.get("duration") or 0
        if dur and dur > max_seconds:
            return f"video too long ({dur}s > {max_seconds}s allowed)"
        return None

    return _filter


def _section_ranges(spec: str):
    """yt-dlp expects a callable producing dicts; we use the simple time-range form."""
    from yt_dlp.utils import parse_duration

    body = spec.lstrip("*")
    start_str, _, end_str = body.partition("-")
    start = parse_duration(start_str) or 0
    end = parse_duration(end_str) if end_str and end_str != "inf" else None

    def _ranges(info_dict, ydl):
        return [{"start_time": start, "end_time": end}]

    return _ranges


def run_download(job_id: str, request: dict[str, Any]) -> dict[str, Any]:
    """RQ entrypoint."""
    settings = get_settings()
    settings.download_dir.mkdir(parents=True, exist_ok=True)

    update_job(job_id, status="downloading", progress=0.0)

    mode = request["mode"]
    ext = "mp3" if mode == "audio" else request.get("container", "mp4")
    outtmpl = str(settings.download_dir / f"{job_id}.%(ext)s")

    opts, tmp_cookies = _build_ydl_opts(job_id, request, outtmpl)
    try:
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(request["url"], download=True)
        title = info.get("title") if isinstance(info, dict) else None

        # yt-dlp may produce a slightly different extension than we predicted
        # (e.g. webm if mp4 muxing falls back). Find the produced file.
        produced = _resolve_output(settings.download_dir, job_id, preferred_ext=ext)
        if produced is None:
            raise RuntimeError("download finished but output file not found")

        size = produced.stat().st_size
        update_job(
            job_id,
            status="completed",
            progress=100.0,
            title=title,
            filename=produced.name,
            size_bytes=size,
            finished_at=time.time(),
            speed=None,
            eta=None,
        )
        return {"job_id": job_id, "filename": produced.name, "size": size}
    except Exception as exc:
        log.exception("job %s failed", job_id)
        # Tag cookie-challenge failures so the frontend can pop a
        # "paste fresh cookies" modal instead of showing the raw yt-dlp
        # error and letting the user flounder.
        error_code = "cookies_required" if is_bot_challenge_error(exc) else None
        update_job(
            job_id,
            status="failed",
            error=str(exc)[:500],
            error_code=error_code,
            finished_at=time.time(),
        )
        raise
    finally:
        cleanup_tmp_cookies(tmp_cookies)


def _resolve_output(directory: Path, job_id: str, preferred_ext: str) -> Path | None:
    pref = directory / f"{job_id}.{preferred_ext}"
    if pref.exists():
        return pref
    # Fall back to anything starting with the job id.
    for p in directory.glob(f"{job_id}.*"):
        if p.is_file():
            return p
    return None
