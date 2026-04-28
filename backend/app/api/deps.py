"""FastAPI dependency helpers."""
from __future__ import annotations

from fastapi import Depends, Header, HTTPException, status

from ..core.security import decode_token
from ..core.users import user_exists


def get_current_user(authorization: str | None = Header(default=None)) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    sub = decode_token(token)
    if not sub or not user_exists(sub):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid token")
    return sub


CurrentUser = Depends(get_current_user)
