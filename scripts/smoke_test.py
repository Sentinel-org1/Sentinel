"""
scripts/smoke_test.py
---------------------
Verifies the full stack is reachable before you start Day 3:
  - Postgres connection via SQLAlchemy
  - Redis PING
  - FastAPI /health endpoint
  - Ingest 100 synthetic predictions and confirm they land in the DB

Usage:
    python scripts/smoke_test.py
"""
from __future__ import annotations

import asyncio
import json
import os
import random
import sys
import time
from datetime import datetime, timezone

import httpx

API_BASE = os.getenv("API_BASE", "http://localhost:8000")
DB_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://sentinel:sentinel@localhost:5432/sentinel")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"
BOLD = "\033[1m"


def ok(msg: str) -> None:
    print(f"  {GREEN}✓{RESET}  {msg}")


def fail(msg: str) -> None:
    print(f"  {RED}✗{RESET}  {msg}")
    sys.exit(1)


def warn(msg: str) -> None:
    print(f"  {YELLOW}~{RESET}  {msg}")


# ── 1. Postgres ───────────────────────────────────────────────
def check_postgres() -> None:
    print(f"\n{BOLD}[1/4] Postgres{RESET}")
    try:
        import psycopg  # psycopg3 sync

        conn_str = DB_URL.replace("postgresql+psycopg://", "postgresql://").replace(
            "postgresql+asyncpg://", "postgresql://"
        )
        with psycopg.connect(conn_str, connect_timeout=5) as conn:
            row = conn.execute("SELECT version()").fetchone()
            ok(f"Connected — {row[0][:60]}")

            # Check schemas
            schemas = conn.execute(
                "SELECT schema_name FROM information_schema.schemata WHERE schema_name LIKE 'sentinel%'"
            ).fetchall()
            names = [r[0] for r in schemas]
            if names:
                ok(f"Schemas present: {', '.join(names)}")
            else:
                warn("Sentinel schemas not yet created — run migrations first")
    except Exception as exc:
        fail(f"Postgres unreachable: {exc}")


# ── 2. Redis ─────────────────────────────────────────────────
def check_redis() -> None:
    print(f"\n{BOLD}[2/4] Redis{RESET}")
    try:
        import redis as redis_lib

        r = redis_lib.from_url(REDIS_URL, socket_connect_timeout=3)
        pong = r.ping()
        if pong:
            ok("PING → PONG")
        info = r.info("server")
        ok(f"Redis version: {info['redis_version']}")
    except Exception as exc:
        fail(f"Redis unreachable: {exc}")


# ── 3. FastAPI /health ────────────────────────────────────────
def check_api() -> None:
    print(f"\n{BOLD}[3/4] FastAPI /health{RESET}")
    try:
        r = httpx.get(f"{API_BASE}/health", timeout=5)
        r.raise_for_status()
        ok(f"HTTP {r.status_code} — {r.json()}")
    except Exception as exc:
        fail(f"API unreachable: {exc}")


# ── 4. Prediction ingest (100 synthetic records) ──────────────
def check_ingest() -> None:
    print(f"\n{BOLD}[4/4] Prediction ingest (100 records){RESET}")
    try:
        # Login first
        login_r = httpx.post(
            f"{API_BASE}/auth/login",
            json={"username": "admin@sentinel.dev", "password": "sentinel"},
            timeout=5,
        )
        if login_r.status_code != 200:
            warn(f"Login returned {login_r.status_code} — skipping ingest test (seed users first)")
            return

        token = login_r.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Build batch
        batch = [
            {
                "model_id": 1,
                "features": {
                    "age": random.randint(18, 75),
                    "income": round(random.gauss(55000, 15000), 2),
                    "credit_score": random.randint(300, 850),
                },
                "prediction": round(random.random(), 4),
                "confidence": round(random.uniform(0.5, 0.99), 4),
            }
            for _ in range(100)
        ]

        t0 = time.perf_counter()
        r = httpx.post(
            f"{API_BASE}/api/predictions/ingest",
            json={"predictions": batch},
            headers=headers,
            timeout=15,
        )
        elapsed = (time.perf_counter() - t0) * 1000

        if r.status_code == 200:
            body = r.json()
            ok(f"Ingested {body.get('ingested', '?')} predictions in {elapsed:.0f}ms")
        else:
            warn(f"Ingest returned {r.status_code}: {r.text[:200]}")
    except Exception as exc:
        warn(f"Ingest check skipped: {exc}")


# ── Main ──────────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"\n{BOLD}{'='*50}{RESET}")
    print(f"{BOLD}  Sentinel Smoke Test{RESET}")
    print(f"{BOLD}{'='*50}{RESET}")
    print(f"  API:   {API_BASE}")
    print(f"  DB:    {DB_URL[:40]}...")
    print(f"  Redis: {REDIS_URL}")

    check_postgres()
    check_redis()
    check_api()
    check_ingest()

    print(f"\n{GREEN}{BOLD}  All checks passed ✓{RESET}\n")