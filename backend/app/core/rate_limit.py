"""
backend/app/core/rate_limit.py
---------------------------------
Rate limiting configuration using slowapi.

Limits:
  - /auth/* endpoints:             20 requests/minute per IP
  - /api/predictions/ingest:      100 requests/minute per IP
  - All other /api/* endpoints:   200 requests/minute per IP
"""
import os
import sys

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import settings

# Use local memory storage during testing, and shared Redis storage in running environment
if "pytest" in sys.modules or os.getenv("PYTEST_CURRENT_TEST") or settings.ENVIRONMENT == "testing":
    storage_uri = "memory://"
else:
    storage_uri = settings.REDIS_URL

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200/minute"],
    storage_uri=storage_uri,
)

# Pre-defined limit strings for use in route decorators
AUTH_LIMIT = "20/minute"
INGEST_LIMIT = "100/minute"
