"""backend/app/config.py — All application settings from environment variables."""
from __future__ import annotations
from pydantic_settings import BaseSettings
from pydantic import field_validator


class Settings(BaseSettings):
    # ── Database ───────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://sentinel:sentinel@localhost:5432/sentinel"

    # ── Redis ──────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # ── Auth ───────────────────────────────────────────────────
    SECRET_KEY: str = "change-me-in-production-use-secrets-manager"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ── Observability ──────────────────────────────────────────
    SENTRY_DSN: str = ""
    ENVIRONMENT: str = "development"  # development | staging | production

    # ── API ────────────────────────────────────────────────────
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    # ── Drift detection tuning ─────────────────────────────────
    EWMA_LAMBDA: float = 0.2          # EWMA smoothing factor (Novel #1)
    EWMA_SIGMA_MULTIPLIER: float = 3.0 # Control limit width (3σ)
    DRIFT_BATCH_SIZE: int = 500        # Trigger drift check after N predictions
    DRIFT_INTERVAL_SECONDS: int = 60   # Or trigger after N seconds
    ALERT_COOLDOWN_SECONDS: int = 600  # 10-minute dedup window

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors(cls, v):
        if isinstance(v, str):
            import json
            return json.loads(v)
        return v

    model_config = {"env_file": ".env", "case_sensitive": True}


settings = Settings()