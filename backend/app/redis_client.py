"""
backend/app/redis_client.py
-----------------------------
Async Redis connection pool with stream consumer-group bootstrap.
"""
from __future__ import annotations

import structlog
from redis.asyncio import Redis, from_url

from app.config import settings

logger = structlog.get_logger()

_redis: Redis | None = None

CONSUMER_GROUP = "sentinel-consumers"
STREAM_PATTERN = "sentinel:predictions:*"


async def get_redis() -> Redis:
    """Return the shared async Redis connection (created on first call)."""
    global _redis
    if _redis is None:
        _redis = from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            max_connections=20,
        )
        logger.info("redis_connected", url=settings.REDIS_URL)
    return _redis


async def close_redis() -> None:
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None
        logger.info("redis_closed")


async def ensure_consumer_group(stream_key: str) -> None:
    """
    Create the consumer group on a stream if it doesn't already exist.
    Called once per model when its stream is first written to.
    """
    redis = await get_redis()
    try:
        await redis.xgroup_create(
            stream_key,
            CONSUMER_GROUP,
            id="0",       # Start reading from the beginning
            mkstream=True,
        )
        logger.info("consumer_group_created", stream=stream_key, group=CONSUMER_GROUP)
    except Exception as exc:
        # BUSYGROUP means the group already exists — that's fine
        if "BUSYGROUP" not in str(exc):
            raise