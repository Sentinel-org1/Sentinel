# ADR 001 — Technology Stack

**Status**: Accepted  
**Date**: 2026-05-23  
**Authors**: Sentinel team

---

## Context

Sentinel monitors production ML models in real time. The platform needs:

1. **High-throughput ingestion** — 15,000+ predictions/sec
2. **Sub-second drift detection** — alert within 2 s of batch arrival
3. **Async background computation** — SHAP attribution without blocking the API
4. **Live dashboard updates** — no polling; push events to the browser
5. **Reproducible local setup** — evaluators must be up in < 5 minutes

---

## Decision

| Layer | Choice | Version |
|-------|--------|---------|
| API framework | **FastAPI** | 0.104 |
| ASGI server | **Uvicorn** | 0.24 |
| Database | **PostgreSQL** | 15 |
| ORM | **SQLAlchemy** (async) | 2.0 |
| Migrations | **Alembic** | 1.12 |
| Cache / Streams | **Redis** | 7 |
| Task queue | **Celery** | 5.3 |
| Frontend | **React 18 + Vite + TypeScript** | — |
| State management | **Zustand** | 4 |
| Charts | **Recharts** | 2 |
| Containerisation | **Docker Compose** | — |

---

## Rationale

### FastAPI over Django or Flask
- Native `async/await` — critical for concurrent drift detection requests
- Pydantic v2 for schema validation with strict mode
- OpenAPI docs auto-generated — doubles as API portfolio piece
- WebSocket support built-in (no Channels needed)

### PostgreSQL with JSONB
- `features` and `shap_attribution` stored as JSONB — queryable without schema changes
- `drift_events` composite index `(model_id, detected_at)` covers the hottest query
- Alembic provides auditable, version-controlled migrations

### Redis Streams (not channels)
- `XADD` / `XREADGROUP` gives us consumer groups and at-least-once delivery
- Dead-letter handling via `XCLAIM` for unacknowledged messages
- Same Redis instance used for Celery broker (different DB indices) and pub/sub

### Celery over asyncio background tasks
- FastAPI background tasks are in-process and not durable
- Celery persists tasks through restarts — critical for SHAP (can take 3–5 s)
- Separate `drift` and `shap` Celery queues allow independent scaling

### React + Recharts over Grafana embed
- Grafana requires users to leave the app context
- Custom charts let us overlay EWMA bands and annotate drift events inline
- Recharts is tree-shakeable and plays well with Tailwind

---

## Alternatives Rejected

| Option | Reason rejected |
|--------|-----------------|
| Django + Channels | ORM is sync-first; Channels adds operational complexity |
| Node.js backend | Weaker scientific Python ecosystem (NumPy, SciPy, SHAP, statsmodels) |
| Go backend | Faster concurrency but much slower development; no SHAP library |
| Kafka instead of Redis Streams | Operational overhead unjustified for < 50 models |
| GraphQL | REST is simpler and sufficient for this data shape |

---

## Consequences

- **Positive**: Fully async API, durable background jobs, live WebSocket push
- **Negative**: Two broker/backend Redis DBs to manage alongside the app Redis
- **Risk**: Celery worker restart loses in-flight tasks → mitigated by `acks_late=True`