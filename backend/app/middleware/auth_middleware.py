"""
backend/app/middleware/auth_middleware.py
------------------------------------------
Starlette middleware that enforces Bearer token authentication on
every /api/* route. Public routes (/health, /docs, /auth/*, /openapi.json)
are exempt.
"""
from __future__ import annotations

from fastapi import Request, status
from fastapi.responses import JSONResponse
from jose import JWTError
from starlette.middleware.base import BaseHTTPMiddleware

from app.services.auth_service import auth_service

# Routes that bypass auth middleware
PUBLIC_PREFIXES = (
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/auth/",
)


class AuthMiddleware(BaseHTTPMiddleware):
    """Validate Bearer token on all /api/* requests."""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Allow public routes through without a token
        if not path.startswith("/api") or any(path.startswith(p) for p in PUBLIC_PREFIXES):
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Missing or malformed Authorization header"},
            )

        token = auth_header.removeprefix("Bearer ")
        try:
            payload = auth_service.decode_token(token, expected_type="access")
            # Attach user_id to request state for use in route handlers
            request.state.user_id = int(payload["sub"])
        except JWTError:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Invalid or expired access token"},
            )

        return await call_next(request)