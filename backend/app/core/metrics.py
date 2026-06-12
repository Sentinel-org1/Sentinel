"""
backend/app/core/metrics.py
-----------------------------
Prometheus metrics registry for Sentinel.

Exposes:
  - Auto-instrumented HTTP request metrics via prometheus-fastapi-instrumentator
  - Custom ML observability counters and histograms

Custom metrics:
  sentinel_predictions_ingested_total   — Counter(model_id, status)
  sentinel_drift_events_total           — Counter(model_id, detector, severity)
  sentinel_alert_resolution_seconds     — Histogram(model_id, severity)
"""
from __future__ import annotations

from prometheus_client import Counter, Histogram, Info

# ── Application info ──────────────────────────────────────────
APP_INFO = Info(
    "sentinel",
    "Sentinel ML Observability Platform build metadata",
)
APP_INFO.info({
    "version": "0.1.0",
    "component": "backend",
})

# ── Custom ML Counters ────────────────────────────────────────
PREDICTIONS_INGESTED = Counter(
    "sentinel_predictions_ingested_total",
    "Total number of predictions ingested into the platform",
    labelnames=["model_id", "status"],
)

DRIFT_EVENTS = Counter(
    "sentinel_drift_events_total",
    "Total drift events detected across all models",
    labelnames=["model_id", "detector", "severity"],
)

# ── Alert resolution latency ─────────────────────────────────
ALERT_RESOLUTION_SECONDS = Histogram(
    "sentinel_alert_resolution_seconds",
    "Time (seconds) between alert creation and resolution",
    labelnames=["model_id", "severity"],
    buckets=[60, 300, 600, 1800, 3600, 7200, 14400, 43200, 86400],
)
