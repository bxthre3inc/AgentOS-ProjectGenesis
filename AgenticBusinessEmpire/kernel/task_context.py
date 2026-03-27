"""
task_context.py — AgenticBusinessEmpire Task Context Object (TCO) schema.

A TCO is the atomic unit of work in AgenticBusinessEmpire.  It is serialised to JSON and
stored on disk so that the kernel is completely stateless between runs.

Required fields
---------------
task_id   : str   — uuid4
tenant    : str   — one of: tenant_zero | product_alpha | subsidiary_beta
priority  : int   — 0 (highest) … 9 (lowest)
payload   : dict  — free-form work description
created_at: str   — ISO-8601 UTC

Optional fields
---------------
tags         : list[str]
deadline_at  : str | None
assigned_agent: str | None
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VALID_TENANTS = {"tenant_zero", "product_alpha", "subsidiary_beta", "generic_template"}


@dataclass
class TaskContext:
    task_id:        str
    tenant:         str
    priority:       int
    payload:        dict[str, Any]
    created_at:     str

    # optional
    tags:            list[str]       = field(default_factory=list)
    deadline_at:     str | None      = None
    assigned_agent:  str | None      = None

    # runtime-populated — not persisted in pending/
    started_at:      str | None      = None
    completed_at:    str | None      = None
    result:          dict | None     = None
    error:           str | None      = None

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    def __post_init__(self) -> None:
        if self.tenant not in VALID_TENANTS:
            raise ValueError(
                f"Invalid tenant '{self.tenant}'. Must be one of {VALID_TENANTS}."
            )
        if not (0 <= self.priority <= 9):
            raise ValueError("priority must be 0–9.")
        if not self.task_id:
            raise ValueError("task_id must not be empty.")

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------
    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, data: dict) -> "TaskContext":
        return cls(**data)

    @classmethod
    def from_json(cls, raw: str) -> "TaskContext":
        return cls.from_dict(json.loads(raw))

    @classmethod
    def from_file(cls, path: Path) -> "TaskContext":
        return cls.from_json(path.read_text())

    def save(self, directory: Path) -> Path:
        directory.mkdir(parents=True, exist_ok=True)
        dest = directory / f"{self.task_id}.json"
        dest.write_text(self.to_json())
        return dest

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------
    @classmethod
    def new(
        cls,
        tenant: str,
        payload: dict,
        priority: int = 5,
        tags: list[str] | None = None,
        deadline_at: str | None = None,
        assigned_agent: str | None = None,
    ) -> "TaskContext":
        return cls(
            task_id=str(uuid.uuid4()),
            tenant=tenant,
            priority=priority,
            payload=payload,
            created_at=datetime.now(timezone.utc).isoformat(),
            tags=tags or [],
            deadline_at=deadline_at,
            assigned_agent=assigned_agent,
        )


# ---------------------------------------------------------------------------
# Quick benchmark helper (used by maintenance_agent)
# ---------------------------------------------------------------------------
def benchmark_roundtrip(n: int = 1_000) -> float:
    """Serialise + deserialise a sample TCO n times.  Returns µs per op."""
    sample = TaskContext.new(
        tenant="tenant_zero",
        payload={"action": "benchmark", "n": n},
        priority=0,
        tags=["benchmark"],
    )
    raw = sample.to_json()
    start = time.perf_counter()
    for _ in range(n):
        TaskContext.from_json(raw)
    elapsed_us = (time.perf_counter() - start) * 1e6 / n
    return elapsed_us
