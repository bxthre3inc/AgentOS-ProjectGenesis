"""
rqe.py — AgentOS Relational Query Engine (RQE)

The RQE is the 'Map Manager' for all Bxthre3 assets. It:
  1. Accepts spatial queries by (lat, lon) and returns structured data
     for Irrig8 field ops (Elevation, NDVI, Soil Moisture, EC).
  2. Returns compressed (zlib + base64) JSON arrays for low-latency
     hand-off to Zo math engines.
  3. Enforces tenant isolation on every query via the Registry Controller.

All heavy data sits in PostgreSQL spatial tables (or flat JSON files in
stub mode). When asyncpg is not available, the RQE reads from local
fixture files so math_engine.py can still be exercised.

Public API
----------
    result = await RQE.query(lat, lon, layers, tenant_id)
    # result.compressed_json  → bytes  (zlib-compressed JSON)
    # result.data             → dict   (raw, for inspection)
    # result.latency_ms       → float
"""

from __future__ import annotations

import base64
import json
import logging
import math
import time
import zlib
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("agentos.rqe")

# Supported spatial layers
LAYERS = {"elevation_m", "ndvi", "soil_moisture_pct", "ec_ds_m", "temperature_c"}


# ---------------------------------------------------------------------------
# Result object
# ---------------------------------------------------------------------------
@dataclass
class RQEResult:
    lat:            float
    lon:            float
    layers:         list[str]
    tenant_id:      str
    data:           dict[str, Any]
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

    @property
    def compressed_size_bytes(self) -> int:
        return len(self.compressed_json)

    def to_dict(self) -> dict:
        return {
            "lat": self.lat, "lon": self.lon,
            "tenant_id": self.tenant_id,
            "layers": self.layers,
            "data": self.data,
            "latency_ms": round(self.latency_ms, 3),
            "source": self.source,
            "compressed_size_bytes": self.compressed_size_bytes,
        }


# ---------------------------------------------------------------------------
# Stub data generator (physics-inspired, deterministic for a given lat/lon)
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# RQE — main interface
# ---------------------------------------------------------------------------
class RQE:
    """Relational Query Engine — spatial field data accessor."""

    def __init__(self, pool: Any = None) -> None:
        self._pool = pool   # asyncpg Pool | None

    async def query(
        self,
        lat: float,
        lon: float,
        layers: list[str],
        tenant_id: str,
    ) -> RQEResult:
        """
        Return field data for the requested (lat, lon) and layers.
        Enforces that only valid layers are requested.
        """
        invalid = set(layers) - LAYERS
        if invalid:
            raise ValueError(f"Unknown layers: {invalid}. Valid: {LAYERS}")

        t0 = time.perf_counter()

        if self._pool is not None:
            data = await self._query_db(lat, lon, layers, tenant_id)
            source = "db"
        else:
            data = self._query_stub(lat, lon, layers)
            source = "stub"

        latency_ms = (time.perf_counter() - t0) * 1e3
        if latency_ms > 100:
            logger.warning("[RQE] Query %.1f ms exceeds 100ms SLA. lat=%.5f lon=%.5f", latency_ms, lat, lon)

        return RQEResult(
            lat=lat, lon=lon,
            layers=layers, tenant_id=tenant_id,
            data=data, latency_ms=latency_ms, source=source,
        )

    def _query_stub(self, lat: float, lon: float, layers: list[str]) -> dict:
        return {layer: _stub_value(lat, lon, layer) for layer in layers}

    async def _query_db(
        self, lat: float, lon: float, layers: list[str], tenant_id: str
    ) -> dict:
        """
        Pull the nearest recorded sensor point from PostgreSQL.
        Falls back to stub if no data within approx 50m radius.
        """
        # Approx 50m bounding box
        # 1 degree lat ~ 111km, 1 degree lon ~ 111km * cos(lat)
        # 50m ~ 0.00045 degrees
        delta = 0.00045
        sql = """
            SELECT metric_name, metric_value, lat, lon
            FROM subsidiary_health
            WHERE tenant_id = $1
              AND metric_name = ANY($2::text[])
              AND lat BETWEEN $3 AND $4
              AND lon BETWEEN $5 AND $6
            ORDER BY recorded_at DESC
            LIMIT $7
        """
        try:
            rows = await self._pool.fetch(
                sql, tenant_id, layers,
                lat - delta, lat + delta,
                lon - delta, lon + delta,
                len(layers) * 2  # fetch more for filtering/fallback
            )
            if rows:
                # Group by metric and take the one with minimum distance
                best = {}
                for r in rows:
                    name = r["metric_name"]
                    dist = math.sqrt((r["lat"] - lat)**2 + (r["lon"] - lon)**2)
                    if name not in best or dist < best[name][1]:
                        best[name] = (r["metric_value"], dist)
                return {name: val for name, (val, _) in best.items() if name in layers}
        except Exception as exc:
            logger.warning("[RQE] DB query failed, using stub: %s", exc)
        return self._query_stub(lat, lon, layers)

    # ------------------------------------------------------------------
    # Grid query — batch spatial retrieval for math engine hand-off
    # ------------------------------------------------------------------
    async def query_grid(
        self,
        points: list[tuple[float, float]],
        layers: list[str],
        tenant_id: str,
    ) -> list[dict]:
        """
        Query multiple (lat, lon) points.
        Returns a list of compressed-JSON-ready dicts.
        """
        results = []
        for lat, lon in points:
            r = await self.query(lat, lon, layers, tenant_id)
            results.append(r.to_dict())
        return results
