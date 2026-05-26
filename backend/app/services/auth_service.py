"""
backend/app/services/auth_service.py
--------------------------------------
JWT creation/verification and password hashing.
Tokens:
  - access  → short-lived (30 min), HS256
  - refresh → long-lived (7 days), stored only in HttpOnly cookie
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.user import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ACCESS_TOKEN_TYPE = "access"
REFRESH_TOKEN_TYPE = "refresh"


class AuthService:
    """Handles JWT lifecycle and password operations."""

    # ── Password helpers ──────────────────────────────────────
    def hash_password(self, password: str) -> str:
        return pwd_context.hash(password)

    def verify_password(self, plain: str, hashed: str) -> bool:
        return pwd_context.verify(plain, hashed)

    # ── Token creation ────────────────────────────────────────
    def _create_token(
        self, subject: str | int, token_type: str, expires_delta: timedelta
    ) -> str:
        expire = datetime.now(timezone.utc) + expires_delta
        payload: dict[str, Any] = {
            "sub": str(subject),
            "type": token_type,
            "exp": expire,
            "iat": datetime.now(timezone.utc),
        }
        return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    def create_access_token(self, user_id: int) -> str:
        return self._create_token(
            user_id,
            ACCESS_TOKEN_TYPE,
            timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        )

    def create_refresh_token(self, user_id: int) -> str:
        return self._create_token(
            user_id,
            REFRESH_TOKEN_TYPE,
            timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )

    # ── Token verification ────────────────────────────────────
    def decode_token(self, token: str, expected_type: str = ACCESS_TOKEN_TYPE) -> dict:
        """
        Decode and validate a JWT.
        Raises JWTError on any failure (expired, bad signature, wrong type).
        """
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("type") != expected_type:
            raise JWTError(f"Token type mismatch: expected {expected_type}")
        return payload

    def get_user_id_from_token(self, token: str) -> int:
        payload = self.decode_token(token, ACCESS_TOKEN_TYPE)
        return int(payload["sub"])

    # ── DB operations ─────────────────────────────────────────
    async def get_user_by_email(self, db: AsyncSession, email: str) -> User | None:
        result = await db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def get_user_by_id(self, db: AsyncSession, user_id: int) -> User | None:
        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def authenticate(
        self, db: AsyncSession, email: str, password: str
    ) -> User | None:
        """Return User if credentials valid, else None."""
        user = await self.get_user_by_email(db, email)
        if not user or not self.verify_password(password, user.hashed_password):
            return None
        if not user.is_active:
            return None
        return user

    async def create_user(
        self, db: AsyncSession, email: str, password: str, is_superuser: bool = False
    ) -> User:
        user = User(
            email=email,
            hashed_password=self.hash_password(password),
            is_superuser=is_superuser,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user


# Module-level singleton
auth_service = AuthService()