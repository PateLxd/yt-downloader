import os

# Configure a fixed user before importing settings.
os.environ.setdefault("AUTH_USERS", "alice:wonderland,bob:builder")
os.environ.setdefault("JWT_SECRET", "test-secret-1234")

from app.core.security import create_access_token, decode_token  # noqa: E402
from app.core.users import authenticate, user_exists  # noqa: E402


def test_authenticate_valid():
    assert authenticate("alice", "wonderland")
    assert authenticate("bob", "builder")


def test_authenticate_invalid():
    assert not authenticate("alice", "wrong")
    assert not authenticate("eve", "anything")


def test_user_exists():
    assert user_exists("alice")
    assert not user_exists("eve")


def test_jwt_roundtrip():
    token = create_access_token("alice")
    assert decode_token(token) == "alice"
    assert decode_token("not-a-token") is None
