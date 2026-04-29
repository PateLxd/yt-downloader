"""Unit tests for app.services.cookies.

Covers the bits we can exercise without a live Redis:

* ``is_bot_challenge_error`` — detection for the yt-dlp error text the
  UI "paste fresh cookies" modal listens on.
* ``apply_cookies_to_opts`` — Redis override takes precedence over the
  file path; Redis outage falls back to the file path; nothing set
  produces no ``cookiefile`` key.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app.services import cookies as cookies_svc


class _FakeRedisBadConnection:
    def get(self, _key):  # noqa: D401 - trivial stub
        raise ConnectionError("redis down (simulated)")

    def set(self, *a, **kw):
        raise ConnectionError("redis down (simulated)")

    def delete(self, *a, **kw):
        raise ConnectionError("redis down (simulated)")

    def ttl(self, *a, **kw):
        raise ConnectionError("redis down (simulated)")


class _FakeRedis:
    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    def get(self, key: str):
        return self._store.get(key)

    def set(self, key: str, value: str, ex: int | None = None) -> None:
        self._store[key] = value

    def delete(self, key: str) -> None:
        self._store.pop(key, None)

    def ttl(self, key: str) -> int:
        return 3600 if key in self._store else -2


@pytest.fixture(autouse=True)
def _reset_settings_cache():
    from app.core.config import get_settings
    get_settings.cache_clear()  # type: ignore[attr-defined]
    yield
    get_settings.cache_clear()  # type: ignore[attr-defined]


def test_bot_challenge_detection_matches_known_phrases():
    for msg in [
        "ERROR: [youtube] xyz: Sign in to confirm you’re not a bot. Use --cookies-from-browser",
        "use --cookies for authentication",
        "Cookies are required for this extractor",
        "Please confirm your age",
    ]:
        assert cookies_svc.is_bot_challenge_error(Exception(msg)), msg


def test_bot_challenge_detection_rejects_unrelated_errors():
    for msg in [
        "HTTP Error 404: Not Found",
        "FFmpeg exited with non-zero status",
        "unable to resolve host",
    ]:
        assert not cookies_svc.is_bot_challenge_error(Exception(msg)), msg


def test_apply_cookies_uses_override_over_file(monkeypatch, tmp_path: Path):
    fake = _FakeRedis()
    fake.set(cookies_svc._KEY, "# Netscape HTTP Cookie File\n")
    monkeypatch.setattr(cookies_svc, "get_redis", lambda: fake)

    opts: dict = {}
    tmp = cookies_svc.apply_cookies_to_opts(opts)
    try:
        assert tmp is not None
        assert opts["cookiefile"] == tmp
        assert Path(tmp).read_text().startswith("# Netscape HTTP Cookie File")
    finally:
        cookies_svc.cleanup_tmp_cookies(tmp)


def test_apply_cookies_falls_back_to_file_path_when_redis_down(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(cookies_svc, "get_redis", lambda: _FakeRedisBadConnection())

    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text("# Netscape HTTP Cookie File\n")
    monkeypatch.setenv("YT_DLP_COOKIES_PATH", str(cookies_file))

    from app.core.config import get_settings
    get_settings.cache_clear()  # type: ignore[attr-defined]

    opts: dict = {}
    tmp = cookies_svc.apply_cookies_to_opts(opts)
    assert tmp is None, "should not have written a temp file"
    assert opts["cookiefile"] == str(cookies_file)


def test_apply_cookies_noop_when_nothing_configured(monkeypatch):
    monkeypatch.setattr(cookies_svc, "get_redis", lambda: _FakeRedis())
    monkeypatch.setenv("YT_DLP_COOKIES_PATH", "")

    from app.core.config import get_settings
    get_settings.cache_clear()  # type: ignore[attr-defined]

    opts: dict = {}
    tmp = cookies_svc.apply_cookies_to_opts(opts)
    assert tmp is None
    assert "cookiefile" not in opts


def test_apply_pot_provider_noop_when_unset(monkeypatch):
    monkeypatch.setenv("POT_PROVIDER_URL", "")
    from app.core.config import get_settings
    get_settings.cache_clear()  # type: ignore[attr-defined]

    opts: dict = {}
    cookies_svc.apply_pot_provider_to_opts(opts)
    assert "extractor_args" not in opts


def test_apply_pot_provider_injects_base_url(monkeypatch):
    monkeypatch.setenv("POT_PROVIDER_URL", "http://pot-provider:4416")
    from app.core.config import get_settings
    get_settings.cache_clear()  # type: ignore[attr-defined]

    opts: dict = {}
    cookies_svc.apply_pot_provider_to_opts(opts)
    args = opts["extractor_args"]
    assert args["youtubepot-bgutilhttp"] == {"base_url": ["http://pot-provider:4416"]}
    # Default behaviour also pins player_client so yt-dlp actually consumes
    # the POT instead of falling through to android/ios first.
    assert args["youtube"]["player_client"] == ["web", "web_safari", "tv"]


def test_apply_pot_provider_respects_custom_player_clients(monkeypatch):
    monkeypatch.setenv("POT_PROVIDER_URL", "http://pot-provider:4416")
    monkeypatch.setenv("YT_DLP_PLAYER_CLIENTS", "web,android")
    from app.core.config import get_settings
    get_settings.cache_clear()  # type: ignore[attr-defined]

    opts: dict = {}
    cookies_svc.apply_pot_provider_to_opts(opts)
    assert opts["extractor_args"]["youtube"]["player_client"] == ["web", "android"]


def test_apply_pot_provider_skips_pinning_when_clients_empty(monkeypatch):
    monkeypatch.setenv("POT_PROVIDER_URL", "http://pot-provider:4416")
    monkeypatch.setenv("YT_DLP_PLAYER_CLIENTS", "")
    from app.core.config import get_settings
    get_settings.cache_clear()  # type: ignore[attr-defined]

    opts: dict = {}
    cookies_svc.apply_pot_provider_to_opts(opts)
    assert "youtube" not in opts["extractor_args"]
    assert opts["extractor_args"]["youtubepot-bgutilhttp"] == {
        "base_url": ["http://pot-provider:4416"]
    }


def test_apply_pot_provider_preserves_existing_extractor_args(monkeypatch):
    monkeypatch.setenv("POT_PROVIDER_URL", "http://pot-provider:4416")
    from app.core.config import get_settings
    get_settings.cache_clear()  # type: ignore[attr-defined]

    # Caller-provided player_client must NOT be overwritten by pinning.
    opts: dict = {
        "extractor_args": {"youtube": {"player_client": ["mweb"]}}
    }
    cookies_svc.apply_pot_provider_to_opts(opts)
    assert opts["extractor_args"]["youtube"] == {"player_client": ["mweb"]}
    assert opts["extractor_args"]["youtubepot-bgutilhttp"] == {
        "base_url": ["http://pot-provider:4416"]
    }


def test_apply_proxy_noop_when_unset(monkeypatch):
    monkeypatch.setenv("YT_DLP_PROXY", "")
    from app.core.config import get_settings
    get_settings.cache_clear()  # type: ignore[attr-defined]

    opts: dict = {}
    cookies_svc.apply_proxy_to_opts(opts)
    assert "proxy" not in opts


def test_apply_proxy_sets_proxy_when_configured(monkeypatch):
    monkeypatch.setenv("YT_DLP_PROXY", "http://user:pass@residential.proxy:8080")
    from app.core.config import get_settings
    get_settings.cache_clear()  # type: ignore[attr-defined]

    opts: dict = {}
    cookies_svc.apply_proxy_to_opts(opts)
    assert opts["proxy"] == "http://user:pass@residential.proxy:8080"


def test_override_round_trip(monkeypatch):
    fake = _FakeRedis()
    monkeypatch.setattr(cookies_svc, "get_redis", lambda: fake)

    assert cookies_svc.get_override() is None
    cookies_svc.save_override("# Netscape HTTP Cookie File\nfoo\n", ttl_seconds=60)
    assert cookies_svc.get_override() == "# Netscape HTTP Cookie File\nfoo\n"
    cookies_svc.clear_override()
    assert cookies_svc.get_override() is None
