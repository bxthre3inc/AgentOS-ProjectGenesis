"""
worksheet.py — Irrig8 Zo Server Worksheet Protocol

A 'Worksheet' is a versioned, signed instruction packet that the Zo server
pushes (OTA) to field Irrig8 Hubs after each completed irrigation cycle.

Hub OTA flow:
  1. Irrigation cycle completes → hub sends CYCLE_COMPLETE event to Zo
  2. Zo generates an updated Worksheet (schedule + valve map + thresholds)
  3. Hub polls /worksheet/current or receives push via MQTT-style relay
  4. Hub applies Worksheet; acknowledges with ACK packet

Worksheet objects are stored as JSON on disk between cycles so the Zo
server is fully stateless on restart.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
class WorksheetStatus(str, Enum):
    PENDING   = "pending"
    DELIVERED = "delivered"
    APPLIED   = "applied"
    FAILED    = "failed"


# ---------------------------------------------------------------------------
# Worksheet data model
# ---------------------------------------------------------------------------
@dataclass
class ValveSchedule:
    valve_id:    str
    open_at:     str   # ISO-8601 UTC
    duration_s:  int
    flow_rate_lpm: float


@dataclass
class Worksheet:
    """
    OTA instruction packet for a single Irrig8 Hub.

    Fields
    ------
    worksheet_id  : globally unique (uuid4)
    hub_id        : target hardware hub
    version       : monotonically increasing int (hub rejects stale versions)
    cycle_ref     : ID of the irrigation cycle that triggered this worksheet
    valve_schedule: ordered list of valve open/close commands
    thresholds    : moisture trigger thresholds per zone (JSON-free-form)
    issued_at     : server generation timestamp
    status        : lifecycle state
    checksum      : SHA-256 of the canonical JSON payload (integrity check)
    """
    worksheet_id:    str
    hub_id:          str
    version:         int
    cycle_ref:       str
    valve_schedule:  list[ValveSchedule]
    thresholds:      dict[str, Any]
    issued_at:       str
    status:          WorksheetStatus = WorksheetStatus.PENDING
    applied_at:      str | None = None
    ack_payload:     dict | None = None
    checksum:        str = field(default="", init=False)

    def __post_init__(self) -> None:
        self.checksum = self._compute_checksum()

    # ------------------------------------------------------------------
    # Integrity
    # ------------------------------------------------------------------
    def _compute_checksum(self) -> str:
        canonical = json.dumps({
            "worksheet_id": self.worksheet_id,
            "hub_id":       self.hub_id,
            "version":      self.version,
            "valve_schedule": [asdict(v) for v in self.valve_schedule],
            "thresholds":   self.thresholds,
            "issued_at":    self.issued_at,
        }, sort_keys=True)
        return hashlib.sha256(canonical.encode()).hexdigest()

    def verify(self) -> bool:
        return self.checksum == self._compute_checksum()

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------
    def to_dict(self) -> dict:
        d = asdict(self)
        d["status"] = self.status.value
        return d

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    def save(self, directory: Path) -> Path:
        directory.mkdir(parents=True, exist_ok=True)
        dest = directory / f"{self.worksheet_id}.json"
        dest.write_text(self.to_json())
        return dest

    @classmethod
    def from_dict(cls, data: dict) -> "Worksheet":
        vs = [ValveSchedule(**v) for v in data.pop("valve_schedule", [])]
        data["status"] = WorksheetStatus(data.get("status", "pending"))
        data.pop("checksum", None)      # recomputed in __post_init__
        return cls(valve_schedule=vs, **data)

    @classmethod
    def from_json(cls, raw: str) -> "Worksheet":
        return cls.from_dict(json.loads(raw))


# ---------------------------------------------------------------------------
# Worksheet Server (Zo-side)
# ---------------------------------------------------------------------------
class WorksheetServer:
    """
    Manages generation and delivery of Worksheets to Irrig8 Hubs.
    All state is persisted to `store_dir` (filesystem).
    """

    def __init__(self, store_dir: Path) -> None:
        self.store_dir = store_dir
        store_dir.mkdir(parents=True, exist_ok=True)
        self._version_cache: dict[str, int] = {}   # hub_id → latest version

    def generate(
        self,
        hub_id: str,
        cycle_ref: str,
        valve_schedule: list[ValveSchedule],
        thresholds: dict[str, Any],
    ) -> Worksheet:
        """Create a new Worksheet for a hub, incrementing its version."""
        version = self._version_cache.get(hub_id, 0) + 1
        self._version_cache[hub_id] = version

        ws = Worksheet(
            worksheet_id=str(uuid.uuid4()),
            hub_id=hub_id,
            version=version,
            cycle_ref=cycle_ref,
            valve_schedule=valve_schedule,
            thresholds=thresholds,
            issued_at=datetime.now(timezone.utc).isoformat(),
        )
        ws.save(self.store_dir / hub_id)
        return ws

    def current(self, hub_id: str) -> Worksheet | None:
        """Return the latest worksheet for a hub, or None."""
        hub_dir = self.store_dir / hub_id
        if not hub_dir.exists():
            return None
        files = sorted(hub_dir.glob("*.json"))
        if not files:
            return None
        return Worksheet.from_json(files[-1].read_text())

    def acknowledge(self, worksheet_id: str, hub_id: str, ack_payload: dict) -> None:
        """Mark a worksheet as applied by the hub."""
        hub_dir = self.store_dir / hub_id
        path = hub_dir / f"{worksheet_id}.json"
        if not path.exists():
            raise FileNotFoundError(f"Worksheet {worksheet_id} not found for hub {hub_id}.")
        ws = Worksheet.from_json(path.read_text())
        ws.status = WorksheetStatus.APPLIED
        ws.applied_at = datetime.now(timezone.utc).isoformat()
        ws.ack_payload = ack_payload
        ws.checksum = ws._compute_checksum()
        path.write_text(ws.to_json())
