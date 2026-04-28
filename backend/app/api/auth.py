"""Auth endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from ..core.security import create_access_token
from ..core.users import authenticate
from ..schemas.jobs import LoginRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest) -> TokenResponse:
    if not authenticate(payload.username, payload.password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid credentials")
    return TokenResponse(access_token=create_access_token(payload.username))
