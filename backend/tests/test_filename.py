from app.api.downloads import _safe_download_name


def test_strips_filesystem_unsafe_chars():
    name = _safe_download_name('hello/world: <good> "quoted" | clip?', ".mp4")
    # / : < > " | ? all stripped, spaces collapsed.
    assert name == "helloworld good quoted clip.mp4"


def test_preserves_unicode():
    # Gujarati title from the user's screenshot — non-ASCII must survive.
    name = _safe_download_name("હાં રે મેં તો નિરખ્યા", ".mp3")
    assert name == "હાં રે મેં તો નિરખ્યા.mp3"


def test_caps_basename_length():
    long = "x" * 500
    name = _safe_download_name(long, ".mp4")
    assert len(name) == 150 + len(".mp4")
    assert name.endswith(".mp4")


def test_empty_title_falls_back():
    assert _safe_download_name("", ".mp4") == "download.mp4"
    assert _safe_download_name("///???", ".mp4") == "download.mp4"


def test_strips_trailing_dots_and_spaces():
    # Windows refuses files ending in '.' or ' '.
    assert _safe_download_name("hello.   ", ".mp4") == "hello.mp4"
