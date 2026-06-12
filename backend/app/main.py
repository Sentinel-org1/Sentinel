"""
backend/app/main.py
--------------------
FastAPI application — startup, middleware stack, router registration.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from prometheus_fastapi_instrumentator import Instrumentator
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

import sentry_sdk
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app.config import settings
from app.core.rate_limit import limiter
from app.middleware.auth_middleware import AuthMiddleware
from app.middleware.logging_middleware import LoggingMiddleware

# Import custom metrics so they are registered in the default prometheus registry
import app.core.metrics  # noqa: F401



@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — startup and graceful shutdown."""
    # ── Startup ───────────────────────────────────────────────
    if settings.SENTRY_DSN:
        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            environment=settings.ENVIRONMENT,
            traces_sample_rate=0.1,
            profiles_sample_rate=0.05,
        )

    yield  # app is running

    # ── Shutdown ──────────────────────────────────────────────
    from app.redis_client import close_redis
    await close_redis()


API_VERSION = "0.1.0"

app = FastAPI(
    title="Sentinel API",
    description="""
## ML Model Observability Platform

Real-time drift detection, anomaly monitoring, and alerting for
production ML models.

### Auth
All `/api/*` endpoints require `Authorization: Bearer <access_token>`.
Obtain a token via `POST /auth/login`.

### Novel Features
- **EWMA adaptive thresholds** — self-tuning control limits
- **Confidence-weighted PSI** — catches weak covariate shifts
- **Drift type classifier** — actionable drift categorisation
- **STL decomposition** — seasonal noise suppression
- **Calibration curves** — data-driven threshold selection
""",
    version=API_VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── Prometheus auto-instrumentation ───────────────────────────
Instrumentator(
    should_group_status_codes=True,
    should_ignore_untemplated=True,
    excluded_handlers=["/health", "/docs", "/redoc", "/openapi.json"],
).instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)

# ── Rate limiting state and handler registration ──────────────
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── Middleware (applied outermost-first) ──────────────────────
# 1. CORS — must be first so pre-flight OPTIONS requests pass through
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# 2. Gzip for large payload responses (drift history, calibration curves)
app.add_middleware(GZipMiddleware, minimum_size=1024)
# 3. Structured logging — logs every request with latency
app.add_middleware(LoggingMiddleware)
# 4. Auth — validates Bearer token on /api/* routes
app.add_middleware(AuthMiddleware)


# ── Health check (no auth required) ──────────────────────────
@app.get("/health", tags=["ops"], include_in_schema=False)
async def health_check():
    return {"status": "ok", "version": API_VERSION}


# ── Routers ───────────────────────────────────────────────────
from app.routers import auth, models, predictions, drift, alerts, calibration, websocket, inference

app.include_router(auth.router,         prefix="/auth",              tags=["auth"])
app.include_router(models.router,       prefix="/api/models",        tags=["models"])
app.include_router(predictions.router,  prefix="/api/predictions",   tags=["predictions"])
app.include_router(drift.router,        prefix="/api/drift",         tags=["drift"])
app.include_router(alerts.router,       prefix="/api/alerts",        tags=["alerts"])
app.include_router(calibration.router,  prefix="/api/models",        tags=["calibration"])
app.include_router(inference.router,    prefix="/api/models",        tags=["inference"])
app.include_router(websocket.router,                                  tags=["realtime"])