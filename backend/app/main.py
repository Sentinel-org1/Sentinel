"""FastAPI application initialization, middleware, and CORS setup."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import sentry_sdk

from app.config import settings
from app.middleware.logging_middleware import LoggingMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle startup and shutdown events."""
    # Startup
    if settings.SENTRY_DSN:
        sentry_sdk.init(dsn=settings.SENTRY_DSN, environment=settings.ENVIRONMENT)
    yield
    # Shutdown


app = FastAPI(
    title="Sentinel API",
    description="ML Model Monitoring Platform",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Logging middleware
app.add_middleware(LoggingMiddleware)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


# Import and include routers
from app.routers import auth, models, predictions, drift, alerts, calibration, websocket

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(models.router, prefix="/api/models", tags=["models"])
app.include_router(predictions.router, prefix="/api/predictions", tags=["predictions"])
app.include_router(drift.router, prefix="/api/drift", tags=["drift"])
app.include_router(alerts.router, prefix="/api/alerts", tags=["alerts"])
app.include_router(calibration.router, prefix="/api/models", tags=["calibration"])
app.include_router(websocket.router, tags=["websocket"])
