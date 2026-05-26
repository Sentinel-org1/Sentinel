"""backend/app/middleware/logging_middleware.py — Structured JSON request/response logging."""
from __future__ import annotations

import time

import structlog
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

logger = structlog.get_logger()


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Logs every request as a structured JSON line:
      {"event": "request", "method": "POST", "path": "/api/...",
       "status": 200, "latency_ms": 12.4, "user_id": 5}
    """

    async def dispatch(self, request: Request, call_next):
        t0 = time.perf_counter()

        response = await call_next(request)

        latency_ms = round((time.perf_counter() - t0) * 1000, 2)
        user_id = getattr(request.state, "user_id", None)

        logger.info(
            "request",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            latency_ms=latency_ms,
            user_id=user_id,
            client=request.client.host if request.client else None,
        )

        # Attach latency header for frontend visibility
        response.headers["X-Process-Time-Ms"] = str(latency_ms)
        return response