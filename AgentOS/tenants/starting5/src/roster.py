"""
roster.py — Starting5 Roster Model

A Roster is a user-configurable team of exactly 5 specialized agents.
Each slot maps to a basketball position metaphor that describes the
agent's functional role in the Starting5 product.

IMPORTANT: This module has ZERO imports from the AgentOS kernel.
The Roster class is completely decoupled from Bxthre3 internal systems.
It does not know about tenants, TCOs, or the inference node.
The only contract is the public Roster/AgentSlot interface.

Positions
---------
  PG  Point Guard    — orchestrator / task router
  SG  Shooting Guard — primary output generator
  SF  Small Forward  — context retrieval / RAG
  PF  Power Forward  — data processing / transform
  C   Center         — memory / state keeper
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Literal

# ---------------------------------------------------------------------------
# Position definitions
# ---------------------------------------------------------------------------
Position = Literal["PG", "SG", "SF", "PF", "C"]

POSITION_ROLES: dict[Position, str] = {
    "PG": "Orchestrator — routes tasks across the lineup",
    "SG": "Output Generator — primary response synthesis",
    "SF": "Context Retriever — RAG and knowledge lookup",
    "PF": "Data Processor — transforms and structures information",
    "C":  "State Keeper — memory, caching, and persistence",
}

ALL_POSITIONS: list[Position] = ["PG", "SG", "SF", "PF", "C"]


# ---------------------------------------------------------------------------
# Agent Slot
# ---------------------------------------------------------------------------
@dataclass
class AgentSlot:
    position:    Position
    name:        str
    model:       str                    # e.g. "gemini-2.5-pro", "local-llm"
    system_prompt: str
    enabled:     bool = True
    created_at:  str  = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def __post_init__(self) -> None:
        if self.position not in ALL_POSITIONS:
            raise ValueError(f"Invalid position '{self.position}'. Must be one of {ALL_POSITIONS}.")
        if not self.name.strip():
            raise ValueError("Agent name must not be empty.")
        if not self.model.strip():
            raise ValueError("model must not be empty.")

    @property
    def role_description(self) -> str:
        return POSITION_ROLES[self.position]

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Roster
# ---------------------------------------------------------------------------
@dataclass
class Roster:
    """
    A complete 5-agent lineup.  One slot per position.

    Usage
    -----
    roster = Roster.create("My Lineup")
    roster.set(AgentSlot("PG", "Alpha", "gemini-2.5-pro", "You are a task router."))
    roster.validate()         # raises if any slot is unfilled
    print(roster.to_json())
    """
    roster_id:  str   = field(default_factory=lambda: str(uuid.uuid4()))
    name:       str   = "Untitled Roster"
    created_at: str   = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    slots:      dict[Position, AgentSlot] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------
    @classmethod
    def create(cls, name: str) -> "Roster":
        _validate_name(name)
        return cls(name=name)

    # ------------------------------------------------------------------
    # Slot management
    # ------------------------------------------------------------------
    def set(self, slot: AgentSlot) -> None:
        """Assign or replace an agent in a position."""
        self.slots[slot.position] = slot

    def get(self, position: Position) -> AgentSlot | None:
        return self.slots.get(position)

    def remove(self, position: Position) -> None:
        self.slots.pop(position, None)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    def validate(self) -> None:
        """Raise if the lineup is incomplete or has disabled slots."""
        missing = [p for p in ALL_POSITIONS if p not in self.slots]
        if missing:
            raise ValueError(f"Roster '{self.name}' is missing positions: {missing}")
        disabled = [p for p, s in self.slots.items() if not s.enabled]
        if disabled:
            raise ValueError(f"Roster '{self.name}' has disabled slots: {disabled}")

    @property
    def is_complete(self) -> bool:
        return all(p in self.slots for p in ALL_POSITIONS)

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------
    def to_dict(self) -> dict:
        return {
            "roster_id":  self.roster_id,
            "name":       self.name,
            "created_at": self.created_at,
            "is_complete": self.is_complete,
            "slots": {pos: slot.to_dict() for pos, slot in self.slots.items()},
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, data: dict) -> "Roster":
        roster = cls(
            roster_id=data["roster_id"],
            name=data["name"],
            created_at=data["created_at"],
        )
        for pos, slot_data in data.get("slots", {}).items():
            roster.slots[pos] = AgentSlot(**{k: v for k, v in slot_data.items()})
        return roster

    @classmethod
    def from_json(cls, raw: str) -> "Roster":
        return cls.from_dict(json.loads(raw))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _validate_name(name: str) -> None:
    if not name or not name.strip():
        raise ValueError("Roster name must not be empty.")
    if len(name) > 80:
        raise ValueError("Roster name must be ≤ 80 characters.")
    if not re.match(r'^[\w\s\-\.]+$', name):
        raise ValueError("Roster name contains invalid characters.")
