from app.workers.runner import _format_for_video


def test_video_best_caps_at_4k_mp4():
    sel = _format_for_video("best", None, "mp4")
    assert "height<=?2160" in sel
    assert "ext=mp4" in sel


def test_video_balanced_1080p():
    sel = _format_for_video("balanced", None, "mp4")
    assert "height<=?1080" in sel


def test_video_saver_480p():
    sel = _format_for_video("saver", None, "mp4")
    assert "height<=?480" in sel


def test_video_custom_height():
    sel = _format_for_video("custom", 720, "mp4")
    assert "height<=?720" in sel


def test_video_webm_no_mp4_constraint():
    sel = _format_for_video("balanced", None, "webm")
    assert "ext=mp4" not in sel


def test_clip_mode_skips_max_duration_filter():
    """Long videos must not be rejected before the clip's range is applied."""
    from app.workers.runner import _build_ydl_opts

    common = {
        "url": "https://example.com",
        "preset": "balanced",
        "max_height": None,
        "container": "mp4",
    }
    video_opts = _build_ydl_opts("j1", {**common, "mode": "video"}, "/tmp/out.%(ext)s")
    clip_opts = _build_ydl_opts(
        "j2",
        {**common, "mode": "clip", "start": "0:00:10", "end": "0:00:30"},
        "/tmp/out.%(ext)s",
    )
    assert "match_filter" in video_opts
    assert "match_filter" not in clip_opts
    assert "download_ranges" in clip_opts
