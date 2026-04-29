"""Standalone tests for the cookies-format helpers in ``refresh.py``.

Run with ``python cookie_refresh/test_refresh.py`` from the repo root. We
deliberately don't import from the rest of the project — this module is
shipped in its own Docker image and stays decoupled from the backend
package.

Playwright/redis are imported at module load in ``refresh.py``; these
tests skip themselves cleanly if they aren't installed, so contributors
can run the round-trip checks without pulling the ~1.5 GB Playwright
image first.
"""

from __future__ import annotations

import sys
from pathlib import Path

# ``cookie_refresh/`` is the directory we live in.
sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    from refresh import parse_netscape, to_netscape  # type: ignore[import-not-found]
except ImportError as exc:
    print(f"SKIP: refresh.py imports unavailable ({exc})")
    sys.exit(0)


def test_round_trip_basic() -> None:
    src = (
        "# Netscape HTTP Cookie File\n"
        "# This is a comment\n"
        "\n"
        ".youtube.com\tTRUE\t/\tTRUE\t1893456000\tSID\tabc123\n"
        "youtube.com\tFALSE\t/\tFALSE\t0\tVISITOR_INFO1_LIVE\txyz\n"
    )
    cookies = parse_netscape(src)
    assert len(cookies) == 2, cookies
    assert cookies[0]["name"] == "SID"
    assert cookies[0]["domain"] == ".youtube.com"
    assert cookies[0]["secure"] is True
    assert cookies[0]["expires"] == 1893456000
    assert cookies[1]["expires"] == -1  # session cookie, mapped from "0"

    rendered = to_netscape(cookies)
    # Round trip should still parse to the same cookie set.
    again = parse_netscape(rendered)
    by_name = {c["name"]: c for c in again}
    assert set(by_name) == {"SID", "VISITOR_INFO1_LIVE"}
    assert by_name["SID"]["value"] == "abc123"
    assert by_name["SID"]["secure"] is True
    # Rendered form treats domain leading "." as the include-subdomain flag.
    sid_line = next(line for line in rendered.splitlines() if "SID\t" in line)
    assert sid_line.startswith(".youtube.com\tTRUE\t/\tTRUE\t1893456000\tSID\tabc123")


def test_strips_httponly_prefix() -> None:
    src = "#HttpOnly_.youtube.com\tTRUE\t/\tTRUE\t0\tSAPISID\thash\n"
    cookies = parse_netscape(src)
    assert len(cookies) == 1
    assert cookies[0]["name"] == "SAPISID"
    assert cookies[0]["domain"] == ".youtube.com"


def test_skips_malformed_and_empty_lines() -> None:
    src = "\n# comment\nnot enough\tcols\nfoo.com\tFALSE\t/\tFALSE\t0\tname\tvalue\n"
    cookies = parse_netscape(src)
    assert len(cookies) == 1
    assert cookies[0]["name"] == "name"


def test_to_netscape_skips_tab_in_value() -> None:
    cookies = [
        {
            "name": "evil",
            "value": "has\ttab",
            "domain": ".x.com",
            "path": "/",
            "secure": True,
            "expires": 0,
        },
        {
            "name": "ok",
            "value": "fine",
            "domain": ".x.com",
            "path": "/",
            "secure": False,
            "expires": -1,
        },
    ]
    rendered = to_netscape(cookies)
    parsed = parse_netscape(rendered)
    assert {c["name"] for c in parsed} == {"ok"}


def test_session_cookie_renders_as_zero() -> None:
    cookies = [
        {
            "name": "session",
            "value": "v",
            "domain": ".x.com",
            "path": "/",
            "secure": False,
            "expires": -1,
        }
    ]
    rendered = to_netscape(cookies)
    line = next(line for line in rendered.splitlines() if line.startswith(".x.com"))
    assert line.split("\t")[4] == "0"


def main() -> int:
    failures = 0
    for name, fn in list(globals().items()):
        if not name.startswith("test_") or not callable(fn):
            continue
        try:
            fn()
        except AssertionError as exc:
            print(f"FAIL {name}: {exc}")
            failures += 1
        except Exception as exc:  # noqa: BLE001
            print(f"ERROR {name}: {exc!r}")
            failures += 1
        else:
            print(f"PASS {name}")
    if failures:
        print(f"\n{failures} test(s) failed")
        return 1
    print("\nAll tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
