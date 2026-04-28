"""Tiny in-memory user store seeded from `AUTH_USERS` env var."""
from __future__ import annotations

from .config import get_settings
from .security import verify_password


def _parse_users(raw: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if not chunk or ":" not in chunk:
            continue
        user, _, secret = chunk.partition(":")
        user = user.strip()
        secret = secret.strip()
        if user and secret:
            out[user] = secret
    return out


def authenticate(username: str, password: str) -> bool:
    users = _parse_users(get_settings().auth_users)
    stored = users.get(username)
    if stored is None:
        return False
    return verify_password(password, stored)


def user_exists(username: str) -> bool:
    return username in _parse_users(get_settings().auth_users)
