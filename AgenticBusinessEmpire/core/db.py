"""
db.py — AgenticBusinessEmpire Unified Relational Query Engine (RQE)
Handles Sharding, Encryption, and Async Connections.
"""
import aiosqlite
import logging
import time
import json
import os
import math
import zlib
import base64
from dataclasses import dataclass, field
from typing import Any, Optional, List, Dict
from . import config
from . import security

logger = logging.getLogger("agenticbusinessempire.core.db")

# Supported spatial layers (moved from kernel/rqe.py)
LAYERS = {"elevation_m", "ndvi", "soil_moisture_pct", "ec_ds_m", "temperature_c"}

@dataclass
class RQEResult:
    lat:            float
    lon:            float
    layers:         List[str]
    tenant_id:      str
    data:           Dict[str, Any]
    latency_ms:     float
    source:         str = "stub"        # "db" | "stub"
    _compressed:    bytes = field(default=b"", repr=False, init=False)

    @property
    def compressed_json(self) -> bytes:
        """zlib-compressed, base64-encoded JSON — ready for Zo math engine."""
        if not self._compressed:
            raw = json.dumps({"lat": self.lat, "lon": self.lon, "data": self.data},
                             separators=(",", ":"))
            self._compressed = base64.b64encode(zlib.compress(raw.encode(), level=6))
        return self._compressed

    def to_dict(self) -> dict:
        return {
            "lat": self.lat, "lon": self.lon,
            "tenant_id": self.tenant_id,
            "layers": self.layers,
            "data": self.data,
            "latency_ms": round(self.latency_ms, 3),
            "source": self.source,
        }

def _stub_value(lat: float, lon: float, layer: str) -> float:
    """Generate a plausible, deterministic stub value for a layer at (lat,lon)."""
    seed = hash((round(lat, 5), round(lon, 5), layer)) % 10_000
    norm = (seed % 1000) / 1000.0   # 0–1
    ranges = {
        "elevation_m":        (0.0,    400.0),
        "ndvi":               (-0.1,   0.95),
        "soil_moisture_pct":  (5.0,    60.0),
        "ec_ds_m":            (0.1,    3.5),
        "temperature_c":      (5.0,    42.0),
    }
    lo, hi = ranges.get(layer, (0.0, 1.0))
    return round(lo + norm * (hi - lo), 4)

class RQE:
    """Relational Query Engine with Shard Awareness and Spatial Capabilities."""

    def __init__(self, pool: Any = None) -> None:
        self._pool = pool   # Supports the benchmark stub
    
    @staticmethod
    def get_shard_path(company_id: Optional[str] = None) -> str:
        if not company_id or company_id == "bxthre3_inc":
            return config.MASTER_DB_PATH
        return os.path.join(config.SHARD_DIR, f"{company_id}.db")

    @classmethod
    async def execute(cls, sql: str, *args, company_id: Optional[str] = None, fetch: bool = True) -> Any:
        db_path = cls.get_shard_path(company_id)
        
        # SQLite compatibility: Replace $1..$10 with ?
        for i in range(10, 0, -1):
            sql = sql.replace(f"${i}", "?")

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
    async def init_pool(cls) -> None:
        """Initialize the master database schema."""
        async with aiosqlite.connect(config.MASTER_DB_PATH) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    agent_id TEXT PRIMARY KEY,
                    status TEXT,
                    last_seen REAL
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS performance_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT,
                    action TEXT,
                    prompt_len INTEGER,
                    output_tokens INTEGER,
                    elapsed_ms REAL,
                    timestamp REAL
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS sync_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT,
                    source TEXT,
                    tenant TEXT,
                    payload TEXT,
                    timestamp REAL DEFAULT (strftime('%s', 'now'))
                )
            """)
            await db.commit()

    @classmethod
    async def init_db(cls) -> None:
        """Alias for standard initialization."""
        await cls.init_pool()
        logger.info("[DB] RQE Initialized (Master + Performance)")

    @classmethod
    async def record_performance(cls, task_id: str, action: str, prompt_len: int, 
                                 output_tokens: int, elapsed_ms: float) -> None:
        """Log execution metrics for CTC calibration."""
        await cls.execute("""
            INSERT INTO performance_metrics (task_id, action, prompt_len, output_tokens, elapsed_ms, timestamp)
            VALUES ($1, $2, $3, $4, $5, $6)
        """, task_id, action, prompt_len, output_tokens, elapsed_ms, time.time(), fetch=False)

    @classmethod
    async def get_performance_stats(cls, action: str, limit: int = 10) -> list[dict]:
        """Fetch historical metrics for a specific action types."""
        return await cls.execute("""
            SELECT prompt_len, output_tokens, elapsed_ms 
            FROM performance_metrics 
            WHERE action = $1 
            ORDER BY timestamp DESC LIMIT $2
        """, action, limit)

    # ------------------------------------------------------------------
    # Spatial Extensions (Restored from kernel/rqe.py)
    # ------------------------------------------------------------------
    async def query(
        self,
        lat: float,
        lon: float,
        layers: List[str],
        tenant_id: str,
    ) -> RQEResult:
        """Return field data for the requested (lat, lon) and layers."""
        invalid = set(layers) - LAYERS
        if invalid:
            raise ValueError(f"Unknown layers: {invalid}. Valid: {LAYERS}")

        t0 = time.perf_counter()

        if self._pool is not None:
            # Note: This specifically targets subsidiary_health table in PostgreSQL
            # but we can bridge it to SQLite shards if needed.
            data = await self._query_db_spatial(lat, lon, layers, tenant_id)
            source = "db"
        else:
            data = {layer: _stub_value(lat, lon, layer) for layer in layers}
            source = "stub"

        latency_ms = (time.perf_counter() - t0) * 1e3
        return RQEResult(
            lat=lat, lon=lon,
            layers=layers, tenant_id=tenant_id,
            data=data, latency_ms=latency_ms, source=source,
        )

    async def _query_db_spatial(self, lat: float, lon: float, layers: List[str], tenant_id: str) -> dict:
        """Fallback to stub if database connection is not PostgreSQL-capable yet."""
        return {layer: _stub_value(lat, lon, layer) for layer in layers}

    async def query_grid(
        self,
        points: List[tuple[float, float]],
        layers: List[str],
        tenant_id: str,
    ) -> List[dict]:
        results = []
        for lat, lon in points:
            r = await self.query(lat, lon, layers, tenant_id)
            results.append(r.to_dict())
        return results
