-- =============================================================
-- Sentinel — Postgres initialisation
-- Creates three schemas so tables stay logically separated.
-- =============================================================

CREATE SCHEMA IF NOT EXISTS sentinel_core;    -- models, predictions, baselines
CREATE SCHEMA IF NOT EXISTS sentinel_metrics; -- drift_events, drift_thresholds, calibration
CREATE SCHEMA IF NOT EXISTS sentinel_alerts;  -- alerts, audit_log

-- Grant the application role access to all schemas
GRANT USAGE ON SCHEMA sentinel_core    TO sentinel;
GRANT USAGE ON SCHEMA sentinel_metrics TO sentinel;
GRANT USAGE ON SCHEMA sentinel_alerts  TO sentinel;

GRANT ALL PRIVILEGES ON ALL TABLES    IN SCHEMA sentinel_core    TO sentinel;
GRANT ALL PRIVILEGES ON ALL TABLES    IN SCHEMA sentinel_metrics TO sentinel;
GRANT ALL PRIVILEGES ON ALL TABLES    IN SCHEMA sentinel_alerts  TO sentinel;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA sentinel_core    TO sentinel;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA sentinel_metrics TO sentinel;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA sentinel_alerts  TO sentinel;

-- Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";