"""Password hashing + JWT utilities."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from jose import JWTError, jwt
from passlib.context import CryptContext

from .config import get_settings

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return _pwd.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    # Support both bcrypt hashes and plaintext (for the `auth_users` env shortcut).
    if hashed.startswith("$2"):
        try:
            return _pwd.verify(plain, hashed)
        except Exception:
            return False
    return plain == hashed


def create_access_token(sub: str, expires_minutes: int | None = None) -> str:
    settings = get_settings()
    expire = datetime.now(tz=UTC) + timedelta(
        minutes=expires_minutes or settings.jwt_expire_minutes
    )
    payload = {"sub": sub, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> str | None:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        sub = payload.get("sub")
        return sub if isinstance(sub, str) else None
    except JWTError:
        return None
