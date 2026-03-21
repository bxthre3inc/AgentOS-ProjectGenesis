"""
inference_node.py — AgentOS Inference Node

The Inference Node processes a single Task Context Object (TCO):
  1. Accepts the TCO.
  2. Routes it to the correct handler by inspecting payload['action'].
  3. Writes the result back to runtime/tasks/completed/<task_id>.json.
  4. If an exception occurs, writes to runtime/tasks/failed/<task_id>.json.

All reasoning logic is intentionally kept in separate handler modules under
AgentOS/kernel/handlers/ to keep this file as a pure dispatcher.
"""

from __future__ import annotations

import json
import logging
import sys
import time
import asyncio
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Resolve paths relative to this file so the module is location-independent.
# ---------------------------------------------------------------------------
_KERNEL_DIR = Path(__file__).parent
_AGENTOS_DIR = _KERNEL_DIR.parent
_RUNTIME_COMPLETED = _AGENTOS_DIR / "runtime" / "tasks" / "completed"
_RUNTIME_FAILED    = _AGENTOS_DIR / "runtime" / "tasks" / "failed"

sys.path.insert(0, str(_KERNEL_DIR))
from task_context import TaskContext
import handlers.evolution_handlers as evo
import handlers.product_handlers as prod
import handlers.subsidiary_handlers as sub
import handlers.reporting_handlers as rep
import handlers.corporate_handlers as corp
import db

logger = logging.getLogger("agentos.inference_node")


# ---------------------------------------------------------------------------
# Built-in action handlers
# ---------------------------------------------------------------------------
def _handle_noop(task: TaskContext) -> dict:
    return {"status": "ok", "message": "noop — nothing to do."}


def _handle_echo(task: TaskContext) -> dict:
    return {"status": "ok", "echo": task.payload}


def _handle_self_audit(task: TaskContext) -> dict:
    """Walk the AgentOS directory tree and return a summary."""
    entries = [str(p.relative_to(_AGENTOS_DIR)) for p in _AGENTOS_DIR.rglob("*")]
    return {"status": "ok", "file_count": len(entries), "files": entries[:100]}


_HANDLERS: dict[str, callable] = {
    "noop":          _handle_noop,
    "echo":          _handle_echo,
    "self_audit":    _handle_self_audit,
    
    # Track-specific handlers
    "optimize":      evo.handle_optimize,
    "maintenance":   evo.handle_maintenance,
    "wire":          prod.handle_wire,
    "simulate":      sub.handle_simulate,
    "report":        rep.handle_report,
    "onboard":       lambda t: asyncio.run(corp.handle_onboard(t)),
    "expense":       lambda t: asyncio.run(corp.handle_expense(t)),
    "budget":        lambda t: asyncio.run(corp.handle_budget(t)),
}


# ---------------------------------------------------------------------------
# Main dispatch
# ---------------------------------------------------------------------------
def process(task: TaskContext) -> dict:
    """
    Dispatch the TCO to the appropriate handler.
    Returns the result dict.  Raises on unrecoverable errors.
    """
    action = task.payload.get("action", "noop")
    handler = _HANDLERS.get(action)
    if handler is None:
        raise NotImplementedError(
            f"No handler registered for action '{action}'. "
            f"Available: {list(_HANDLERS.keys())}"
        )

    task.started_at = datetime.now(timezone.utc).isoformat()
    t0 = time.perf_counter()

    try:
        result = handler(task)
        elapsed_ms = (time.perf_counter() - t0) * 1e3
        task.completed_at = datetime.now(timezone.utc).isoformat()
        task.result = {**result, "_elapsed_ms": round(elapsed_ms, 3)}
        _persist(task, _RUNTIME_COMPLETED)
        
        # Recursive Audit Log
        if db._pool:
            sql = """
                INSERT INTO recursive_logs (patch_id, target_file, description, diff_summary, outcome, meta)
                VALUES ($1, $2, $3, $4, $5, $6::jsonb)
                ON CONFLICT (patch_id) DO NOTHING
            """
            import asyncio
            asyncio.run(db.execute(
                sql, task.task_id, result.get("target", "kernel"),
                task.payload.get("goal"), str(result.get("optimization") or result.get("action")),
                "success", json.dumps(task.result), fetch=False
            ))
            
        logger.info("Task %s completed in %.2f ms.", task.task_id, elapsed_ms)
        return task.result

    except Exception as exc:
        task.error = str(exc)
        task.completed_at = datetime.now(timezone.utc).isoformat()
        _persist(task, _RUNTIME_FAILED)
        logger.error("Task %s failed: %s", task.task_id, exc)
        raise


def _persist(task: TaskContext, dest_dir: Path) -> None:
    dest_dir.mkdir(parents=True, exist_ok=True)
    path = dest_dir / f"{task.task_id}.json"
    path.write_text(task.to_json())
