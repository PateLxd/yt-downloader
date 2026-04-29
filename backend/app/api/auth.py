"""Auth endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from ..core.config import get_settings
from ..core.security import create_access_token
from ..core.users import authenticate
from ..schemas.jobs import LoginRequest, TokenResponse
from ..services import cookies as cookies_svc
from .deps import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest) -> TokenResponse:
    if not authenticate(payload.username, payload.password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid credentials")
    return TokenResponse(access_token=create_access_token(payload.username))


class CookiesPayload(BaseModel):
    content: str = Field(min_length=1, max_length=1_000_000)


class CookiesStatus(BaseModel):
    present: bool
    # Remaining TTL in seconds if a runtime override exists. -1 when the
    # override has no TTL or the key isn't present.
    expires_in_seconds: int | None = None
    source: str  # "override" | "file" | "none"


def _validate_cookies(content: str) -> str:
    """Return the trimmed content after a cheap sanity check.

    We don't try to fully parse the Netscape format — yt-dlp will do that
    and surface a useful error if it's malformed. We only reject values
    that are obviously not cookies.txt to catch copy-paste accidents.
    """
    stripped = content.strip()
    if not stripped:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "empty cookies content")
    first_line = stripped.splitlines()[0].strip().lower()
    if "netscape" not in first_line and "http cookie file" not in first_line:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "expected Netscape-format cookies.txt (first line should start with '# Netscape HTTP Cookie File')",
        )
    # yt-dlp wants a trailing newline; preserve the user-supplied content
    # otherwise so hashes/whitespace stay exactly as exported.
    return content if content.endswith("\n") else content + "\n"


@router.post("/cookies", response_model=CookiesStatus)
def save_cookies(
    payload: CookiesPayload,
    user: str = Depends(get_current_user),
) -> CookiesStatus:
    """Store a user-pasted cookies.txt for yt-dlp to use on subsequent requests.

    Any authenticated user can update the global override — this is a
    single-tenant / small-team app, and every authenticated user already
    has access to the same download pipeline.
    """
    content = _validate_cookies(payload.content)
    ttl = get_settings().cookies_override_ttl_seconds
    cookies_svc.save_override(content, ttl_seconds=ttl)
    return CookiesStatus(present=True, expires_in_seconds=ttl, source="override")


@router.get("/cookies", response_model=CookiesStatus)
def cookies_status(user: str = Depends(get_current_user)) -> CookiesStatus:
    if cookies_svc.get_override() is not None:
        return CookiesStatus(
            present=True,
            expires_in_seconds=cookies_svc.override_ttl(),
            source="override",
        )
    settings = get_settings()
    if settings.yt_dlp_cookies_path:
        return CookiesStatus(present=True, source="file")
    return CookiesStatus(present=False, source="none")


@router.delete("/cookies", response_model=CookiesStatus)
def clear_cookies(user: str = Depends(get_current_user)) -> CookiesStatus:
    cookies_svc.clear_override()
    # Mirror the GET fallthrough: clearing the runtime override does not mean
    # we have *no* cookies — the on-disk YT_DLP_COOKIES_PATH file (if
    # configured) becomes the active source again.
    settings = get_settings()
    if settings.yt_dlp_cookies_path:
        return CookiesStatus(present=True, source="file")
    return CookiesStatus(present=False, source="none")
