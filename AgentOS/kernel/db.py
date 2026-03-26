"""
db.py — AgentOS Relational Query Engine
Zo-native PostgreSQL state store.

Design targets
--------------
- Query latency p50 ≤ 100 ms (Zo-local, same-host Postgres)
- Async-first: all public APIs are `async def`
- Tenant-isolated: every query surfaces a `tenant_id` constraint
- Connection pool: tuned for single-node Zo instance (max 10 conns)

Dependencies (add to requirements.txt)
---------------------------------------
    asyncpg>=0.29
    python-dotenv>=1.0

Environment variables (set in .env or systemd unit)
-----------------------------------------------------
    AGENTOS_DB_DSN   postgresql://user:pass@localhost:5432/agentos
    AGENTOS_DB_POOL_MIN   2
    AGENTOS_DB_POOL_MAX   10
"""

from __future__ import annotations

import logging
import os
import time
from contextlib import asynccontextmanager
from typing import Any

logger = logging.getLogger("agentos.db")

# ---------------------------------------------------------------------------
# Optional asyncpg import — degrades gracefully for dry-run environments
# ---------------------------------------------------------------------------
try:
    import aiosqlite                          # type: ignore
    _SQLITE_AVAILABLE = True
except ImportError:
    aiosqlite = None                          # type: ignore
    _SQLITE_AVAILABLE = False
    logger.warning("aiosqlite not installed — DB layer running in STUB mode.")

# ---------------------------------------------------------------------------
# Connection string (local file for standalone)
# ---------------------------------------------------------------------------
_AGENTOS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DB_PATH = os.path.join(_AGENTOS_DIR, "runtime", "agentos.db")
_pool: Any = None   # For sqlite, we'll manage a persistent connection or simple calls

# ---------------------------------------------------------------------------
# Pool singleton
# ---------------------------------------------------------------------------
_pool: Any = None   # asyncpg.Pool | None

_DSN      = os.getenv("AGENTOS_DB_DSN",     "postgresql://agentos:agentos@localhost:5432/agentos")
_POOL_MIN = int(os.getenv("AGENTOS_DB_POOL_MIN", "2"))
_POOL_MAX = int(os.getenv("AGENTOS_DB_POOL_MAX", "10"))

# 100 ms hard ceiling — every query that exceeds this logs a warning
LATENCY_TARGET_MS = 100.0


async def init_pool() -> None:
    """Initialize SQLite connection for standalone mode."""
    global _pool
    if not _SQLITE_AVAILABLE:
        logger.info("[DB] Stub mode — connection not initialized.")
        return
    # For SQLite, we don't need a heavy pool, but we'll ensure runtime/ exists
    os.makedirs(os.path.dirname(_DB_PATH), exist_ok=True)
    logger.info("[DB] SQLite Ready (Chromebox Profile) → %s", _DB_PATH)


async def close_pool() -> None:
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
        logger.info("[DB] Pool closed.")


# ---------------------------------------------------------------------------
# Query executor
# ---------------------------------------------------------------------------
async def execute(
    sql: str,
    *args,
    tenant_id: str | None = None,
    fetch: bool = True,
) -> list[dict] | str:
    """
    Run a parameterised query with SQLite.
    """
    if not _SQLITE_AVAILABLE:
        logger.debug("[DB STUB] sql=%s  args=%s", sql[:80], args)
        return [] if fetch else "STUB_OK"

    # SQLite uses ? instead of $1
    sql = sql.replace("$1", "?").replace("$2", "?").replace("$3", "?").replace("$4", "?").replace("$5", "?").replace("$6", "?")

    t0 = time.perf_counter()
    try:
        async with aiosqlite.connect(_DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            if fetch:
                async with db.execute(sql, args) as cursor:
                    rows = await cursor.fetchall()
                    result = [dict(r) for r in rows]
            else:
                await db.execute(sql, args)
                await db.commit()
                result = "OK"
        
        elapsed = (time.perf_counter() - t0) * 1e3
        _check_latency(elapsed, sql)
        return result
    except Exception as exc:
        elapsed = (time.perf_counter() - t0) * 1e3
        logger.error("[DB] Query failed after %.1f ms: %s", elapsed, exc)
        raise


def _check_latency(elapsed_ms: float, sql: str) -> None:
    if elapsed_ms > LATENCY_TARGET_MS:
        logger.warning(
            "[DB] ⚠ Latency %.1f ms exceeds %.0f ms target. SQL: %.80s",
            elapsed_ms, LATENCY_TARGET_MS, sql,
        )
    else:
        logger.debug("[DB] Query %.1f ms  OK.", elapsed_ms)


# ---------------------------------------------------------------------------
# Tenant-scoped helpers
# ---------------------------------------------------------------------------
async def get_tasks(tenant_id: str, status: str = "pending") -> list[dict]:
    sql = "SELECT * FROM tasks WHERE tenant_id = $1 AND status = $2 ORDER BY priority, created_at"
    return await execute(sql, tenant_id, status, tenant_id=tenant_id)


async def upsert_task(task_dict: dict) -> None:
    sql = """
        INSERT INTO tasks (task_id, tenant_id, priority, payload, status, created_at)
        VALUES ($1, $2, $3, $4::jsonb, $5, $6)
        ON CONFLICT (task_id) DO UPDATE
            SET status = EXCLUDED.status,
                payload = EXCLUDED.payload
    """
    import json
    await execute(
        sql,
        task_dict["task_id"],
        task_dict["tenant"],
        task_dict["priority"],
        json.dumps(task_dict["payload"]),
        task_dict.get("status", "pending"),
        task_dict["created_at"],
        fetch=False,
    )


async def get_tenant_metrics(tenant_id: str) -> dict:
    sql = """
        SELECT
            COUNT(*)                               AS total_tasks,
            COUNT(*) FILTER (WHERE status='pending')   AS pending,
            COUNT(*) FILTER (WHERE status='completed') AS completed,
            AVG(EXTRACT(EPOCH FROM (completed_at - started_at)) * 1000)
                                                   AS avg_latency_ms
        FROM tasks
        WHERE tenant_id = $1
    """
    rows = await execute(sql, tenant_id, tenant_id=tenant_id)
    return rows[0] if rows else {}


# ---------------------------------------------------------------------------
# Schema bootstrap (idempotent DDL)
# ---------------------------------------------------------------------------
_DDL = """
CREATE TABLE IF NOT EXISTS tasks (
    task_id        TEXT        PRIMARY KEY,
    tenant_id      TEXT        NOT NULL,
    priority       SMALLINT    NOT NULL DEFAULT 5,
    payload        JSONB       NOT NULL DEFAULT '{}',
    status         TEXT        NOT NULL DEFAULT 'pending',
    created_at     TIMESTAMPTZ NOT NULL,
    started_at     TIMESTAMPTZ,
    completed_at   TIMESTAMPTZ,
    error          TEXT
);

CREATE INDEX IF NOT EXISTS idx_tasks_tenant_status
    ON tasks (tenant_id, status, priority);
"""


from AgentOS.kernel import schema

async def migrate() -> None:
    """Apply schema DDL. Safe to call on every startup."""
    if not _SQLITE_AVAILABLE:
        logger.info("[DB MIGRATE] Stub mode — skipping DDL.")
        return
    
    # Initialize schema using the new master ledger helper
    await schema.apply()
    
    logger.info("[DB MIGRATE] SQLite Schema up to date (Chromebox Profile).")
