from __future__ import annotations

import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.mark.asyncio
async def test_metrics_endpoint():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        r = await client.get("/metrics")
        assert r.status_code == 200
        assert "sentinel_predictions_ingested_total" in r.text
        assert "sentinel_drift_events_total" in r.text
        assert "sentinel_alert_resolution_seconds" in r.text

@pytest.mark.asyncio
async def test_rate_limiting_login():
    from app.core.rate_limit import limiter
    from unittest.mock import patch, AsyncMock
    limiter.reset()

    with patch("app.routers.auth.auth_service.authenticate", new_callable=AsyncMock) as mock_auth:
        mock_auth.return_value = None

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            # The limit is 20/minute.
            # Send 20 requests — they should return 401 Unauthorized (since authenticate returns None), but NOT 429.
            # Send 21st request — it should return 429.
            responses = []
            for _ in range(22):
                r = await client.post("/auth/login", data={"username": "test", "password": "pwd"})
                responses.append(r.status_code)
            
            assert 429 in responses
            assert responses[-1] == 429

