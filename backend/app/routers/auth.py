"""
backend/app/routers/auth.py
----------------------------
Authentication endpoints:
  POST /auth/login    → access + refresh tokens
  POST /auth/refresh  → new access token from refresh cookie
  POST /auth/logout   → clears refresh cookie
  GET  /auth/me       → current user info
"""


from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Response, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from jose import JWTError
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.auth_service import auth_service
from app.core.rate_limit import limiter, AUTH_LIMIT

router = APIRouter()

REFRESH_COOKIE_NAME = "sentinel_refresh"
COOKIE_MAX_AGE = int(timedelta(days=7).total_seconds())


# ── Schemas ────────────────────────────────────────────────────
class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: int
    email: str
    is_superuser: bool

    model_config = {"from_attributes": True}


# ── Endpoints ──────────────────────────────────────────────────
@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login and receive JWT tokens",
)
@limiter.limit(AUTH_LIMIT)
async def login(
    request: Request,
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(OAuth2PasswordRequestForm),
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    OAuth2-compatible login.
    - Returns an access token in the response body.
    - Sets the refresh token as an HttpOnly cookie (never in JS).
    """
    user = await auth_service.authenticate(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = auth_service.create_access_token(user.id)
    refresh_token = auth_service.create_refresh_token(user.id)

    # Refresh token goes in HttpOnly cookie — never accessible to JS
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh_token,
        httponly=True,
        secure=True,       # HTTPS only in production
        samesite="strict",
        max_age=COOKIE_MAX_AGE,
        path="/auth",      # Scope cookie to /auth routes only
    )

    return TokenResponse(access_token=access_token)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Silently refresh an expired access token",
)
async def refresh(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    Reads the HttpOnly refresh cookie and issues a new access token.
    No body required.
    """
    token = request.cookies.get(REFRESH_COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No refresh token")

    try:
        payload = auth_service.decode_token(token, expected_type="refresh")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token")

    user = await auth_service.get_user_by_id(db, int(payload["sub"]))
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User inactive or deleted")

    return TokenResponse(access_token=auth_service.create_access_token(user.id))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, response_class=Response, summary="Clear session")
async def logout(response: Response):
    """Delete the refresh cookie."""
    response.delete_cookie(key=REFRESH_COOKIE_NAME, path="/auth")


@router.get("/me", response_model=UserResponse, summary="Current user info")
async def me(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """
    Requires a valid Bearer access token in the Authorization header.
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token")

    token = auth_header.removeprefix("Bearer ")
    try:
        user_id = auth_service.get_user_id_from_token(token)
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    user = await auth_service.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    return UserResponse.model_validate(user)