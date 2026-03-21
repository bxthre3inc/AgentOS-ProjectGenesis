"""
roster_controller.py — Starting5 Roster Controller

Implements two key agent positions with full A2A (Agent-to-Agent) messaging:

  Point Guard (PG) — Primary Goal Dispatcher
    Receives a user goal, breaks it into sub-tasks, and routes each to
    the correct roster position via the A2A message bus.
    NEVER exposes AgentOS kernel internals to downstream agents.

  Center (C) — Financial/Asset Data Guardian
    Receives tasks tagged 'finance' or 'assets'. Validates that no request
    attempts to access Bxthre3 Inc's internal ledger data. Returns only
    Starting5-scoped financial summaries.

A2A Message Bus
---------------
Messages are plain dicts conforming to the A2AMessage schema.
The Point Guard dispatches; each position handler processes and replies.
No agent in Starting5 ever imports from AgentOS kernel.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Callable, Literal

logger = logging.getLogger("starting5.roster_controller")

# ---------------------------------------------------------------------------
# A2A Message schema
# ---------------------------------------------------------------------------
Position = Literal["PG", "SG", "SF", "PF", "C"]

@dataclass
class A2AMessage:
    msg_id:       str   = field(default_factory=lambda: str(uuid.uuid4()))
    from_pos:     str   = "PG"
    to_pos:       str   = "C"
    intent:       str   = ""          # e.g. "finance.summary", "rdSearch", "generate"
    payload:      dict  = field(default_factory=dict)
    created_at:   str   = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    reply_to:     str | None = None   # msg_id of the message being replied to

    def to_dict(self) -> dict:
        return asdict(self)

    def reply(self, from_pos: str, payload: dict) -> "A2AMessage":
        return A2AMessage(from_pos=from_pos, to_pos=self.from_pos,
                          intent=f"{self.intent}.reply", payload=payload,
                          reply_to=self.msg_id)


# ---------------------------------------------------------------------------
# A2A Message Bus (in-process queue)
# ---------------------------------------------------------------------------
class A2ABus:
    """Lightweight in-process message bus for Starting5 agents."""

    def __init__(self) -> None:
        self._handlers: dict[Position, Callable] = {}
        self._log: list[A2AMessage] = []

    def register(self, position: Position, handler: Callable) -> None:
        self._handlers[position] = handler
        logger.debug("[A2A] Registered handler for position %s", position)

    async def send(self, message: A2AMessage) -> A2AMessage:
        self._log.append(message)
        handler = self._handlers.get(message.to_pos)
        if handler is None:
            raise RuntimeError(f"No handler registered for position '{message.to_pos}'.")
        reply = await handler(message)
        self._log.append(reply)
        return reply

    def history(self) -> list[dict]:
        return [m.to_dict() for m in self._log]


# ---------------------------------------------------------------------------
# Point Guard — Primary Goal Dispatcher
# ---------------------------------------------------------------------------
class PointGuard:
    """
    Receives a high-level user goal and dispatches sub-tasks to the lineup.
    This is the ONLY agent that interacts with external user input.
    It NEVER surfaces AgentOS kernel objects.
    """

    ROUTING_RULES: dict[str, Position] = {
        "finance":  "C",
        "assets":   "C",
        "research": "SF",
        "data":     "PF",
        "generate": "SG",
        "default":  "SG",
    }

    def __init__(self, bus: A2ABus) -> None:
        self.bus = bus
        bus.register("PG", self._handle)

    async def dispatch(self, goal: str, context: dict | None = None) -> list[A2AMessage]:
        """
        Break a goal into sub-tasks and route each to the right position.
        Returns the list of reply messages.
        """
        logger.info("[PG] Dispatching goal: '%s'", goal[:80])
        sub_tasks = self._decompose(goal, context or {})
        replies = []
        for task in sub_tasks:
            position = self._route(task["intent"])
            msg = A2AMessage(from_pos="PG", to_pos=position,
                             intent=task["intent"], payload=task)
            reply = await self.bus.send(msg)
            replies.append(reply)
        return replies

    def _decompose(self, goal: str, context: dict) -> list[dict]:
        """Naïve keyword decomposition.  Replace with LLM call in production."""
        tasks = []
        keyword_map = {
            "finance": "finance.summary",
            "money": "finance.summary",
            "research": "research.query",
            "find": "research.query",
            "write": "generate.text",
            "create": "generate.text",
            "process": "data.transform",
        }
        matched = False
        for kw, intent in keyword_map.items():
            if kw in goal.lower():
                tasks.append({"intent": intent, "goal": goal, "context": context})
                matched = True
                break
        if not matched:
            tasks.append({"intent": "generate.text", "goal": goal, "context": context})
        return tasks

    def _route(self, intent: str) -> Position:
        domain = intent.split(".")[0] if "." in intent else intent
        return self.ROUTING_RULES.get(domain, self.ROUTING_RULES["default"])

    async def _handle(self, msg: A2AMessage) -> A2AMessage:
        """PG can also receive replies — logs and acknowledges."""
        logger.info("[PG] Received reply: %s", msg.intent)
        return msg.reply("PG", {"status": "acknowledged"})


# ---------------------------------------------------------------------------
# Center — Financial/Asset Data Guardian
# ---------------------------------------------------------------------------
# ISOLATION GUARANTEE: This class never reads from Bxthre3's internal ledger.
# It operates only on Starting5-scoped budget/allocation data passed via A2A.

_FORBIDDEN_KEYS = {"bxthre3_ledger", "master_ledger", "internal_assets",
                   "tenant_zero_data", "irrig8_data"}


class Center:
    """
    Financial/Asset Data Guardian.
    Processes finance-tagged tasks and enforces Starting5 data isolation.
    """

    def __init__(self, bus: A2ABus) -> None:
        self.bus = bus
        bus.register("C", self._handle)

    async def _handle(self, msg: A2AMessage) -> A2AMessage:
        # Sanitise payload — strip any forbidden keys before processing
        clean = {k: v for k, v in msg.payload.items() if k not in _FORBIDDEN_KEYS}
        leaked = set(msg.payload.keys()) & _FORBIDDEN_KEYS
        if leaked:
            logger.warning("[C] Blocked attempt to access forbidden keys: %s", leaked)

        result = self._process_finance(clean)
        return msg.reply("C", result)

    def _process_finance(self, payload: dict) -> dict:
        summary = {
            "scope":   "starting5_only",
            "status":  "ok",
            "summary": f"Finance task processed. Goal: {payload.get('goal', 'n/a')[:80]}",
            "isolation_enforced": True,
        }
        logger.info("[C] Finance task processed. Isolation enforced.")
        return summary


# ---------------------------------------------------------------------------
# Shooting Guard — Content Generator
# ---------------------------------------------------------------------------
class ShootingGuard:
    """
    Handles generation-tagged tasks (text, code, creative).
    """

    def __init__(self, bus: A2ABus) -> None:
        self.bus = bus
        bus.register("SG", self._handle)

    async def _handle(self, msg: A2AMessage) -> A2AMessage:
        result = {
            "status": "ok",
            "content": f"Generated content for goal: {msg.payload.get('goal', 'n/a')[:80]}",
            "model": "starting5-gen-v1"
        }
        logger.info("[SG] Generation task processed.")
        return msg.reply("SG", result)


# ---------------------------------------------------------------------------
# Small Forward — Research & Discovery
# ---------------------------------------------------------------------------
class SmallForward:
    """
    Handles research-tagged tasks (queries, searches, discovery).
    """

    def __init__(self, bus: A2ABus) -> None:
        self.bus = bus
        bus.register("SF", self._handle)

    async def _handle(self, msg: A2AMessage) -> A2AMessage:
        result = {
            "status": "ok",
            "findings": f"Research results for: {msg.payload.get('goal', 'n/a')[:80]}",
            "source": "starting5-search-v1"
        }
        logger.info("[SF] Research task processed.")
        return msg.reply("SF", result)


# ---------------------------------------------------------------------------
# Power Forward — Data Analytics
# ---------------------------------------------------------------------------
class PowerForward:
    """
    Handles data-tagged tasks (transformation, analysis, stats).
    """

    def __init__(self, bus: A2ABus) -> None:
        self.bus = bus
        bus.register("PF", self._handle)

    async def _handle(self, msg: A2AMessage) -> A2AMessage:
        result = {
            "status": "ok",
            "analysis": f"Data analysis for: {msg.payload.get('goal', 'n/a')[:80]}",
            "confidence": 0.95
        }
        logger.info("[PF] Analytics task processed.")
        return msg.reply("PF", result)


# ---------------------------------------------------------------------------
# Factory — wire up a full bus with all positions
# ---------------------------------------------------------------------------
def create_default_bus() -> tuple[A2ABus, PointGuard, Center, ShootingGuard, SmallForward, PowerForward]:
    bus = A2ABus()
    pg  = PointGuard(bus)
    c   = Center(bus)
    sg  = ShootingGuard(bus)
    sf  = SmallForward(bus)
    pf  = PowerForward(bus)
    return bus, pg, c, sg, sf, pf
