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
