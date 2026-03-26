"""
db.py — AgentOS Unified Relational Query Engine (RQE)
Handles Sharding, Encryption, and Async Connections.
"""
import aiosqlite
import logging
import time
import json
from typing import Any, Optional
from . import config
from . import security # Assume we'll move SecureData here

logger = logging.getLogger("agentos.core.db")

class RQE:
    """Relational Query Engine with Shard Awareness."""
    
    @staticmethod
    def get_shard_path(company_id: Optional[str] = None) -> str:
        if not company_id or company_id == "bxthre3_inc":
            return config.MASTER_DB_PATH
        return os.path.join(config.SHARD_DIR, f"{company_id}.db")

    @classmethod
    async def execute(cls, sql: str, *args, company_id: Optional[str] = None, fetch: bool = True) -> Any:
        db_path = cls.get_shard_path(company_id)
        
        # SQLite compatibility
        sql = sql.replace("$1", "?").replace("$2", "?").replace("$3", "?") \
                 .replace("$4", "?").replace("$5", "?").replace("$6", "?")

        t0 = time.perf_counter()
        try:
            async with aiosqlite.connect(db_path) as db:
                db.row_factory = aiosqlite.Row
                if fetch:
                    async with db.execute(sql, args) as cursor:
                        rows = await cursor.fetchall()
                        result = [dict(r) for r in rows]
                else:
                    await db.execute(sql, args)
                    await db.commit()
                    result = "OK"
            
            elapsed = (time.perf_counter() - t0) * 1000
            if elapsed > 100:
                logger.warning("[DB] Slow query (%.1fms): %s", elapsed, sql[:50])
            return result
        except Exception as e:
            logger.error("[DB] Query ERROR (%.1fms) on shard %s: %s", (time.perf_counter()-t0)*1000, company_id, e)
            raise

    @classmethod
    async def log_event(cls, event_type: str, source: str, tenant: str = "tenant_zero", payload: dict = None) -> None:
        """Standardized event logging for the mesh."""
        await cls.execute("""
            INSERT INTO sync_events (event_type, source, tenant, payload)
            VALUES ($1, $2, $3, $4)
        """, event_type, source, tenant, json.dumps(payload or {}), fetch=False)

    @classmethod
    async def update_agent_session(cls, agent_id: str, status: str) -> None:
        """Update agent status in the master registry."""
        await cls.execute("""
            INSERT INTO sessions (agent_id, status, last_seen)
            VALUES ($1, $2, $3)
            ON CONFLICT(agent_id) DO UPDATE SET status=$2, last_seen=$3
        """, agent_id, status, time.time(), fetch=False)

    @classmethod
    async def get_recent_events(cls, limit: int = 50) -> list[dict]:
        """Fetch recent sync events."""
        return await cls.execute("SELECT * FROM sync_events ORDER BY id DESC LIMIT $1", limit)

    @classmethod
    async def init_db(cls) -> None:
        """Alias for standard initialization."""
        # This can be used to run DDLs from schema.py if needed
        logger.info("[DB] RQE Initialized")
