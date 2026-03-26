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
from handlers import specialized_prompts as prompts
from handlers import persona_registry as registry
import handlers.workforce_handlers as work
import handlers.strategy_handlers as strategy
import db

import re
import os
import psutil # Add to requirements.txt if not present
import resource_monitor
from resource_monitor import PerformanceProfile
import ctc_engine

# Link to peer bridge for mesh-wide status
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "sync_engine"))
try:
    from sync_engine import peer_bridge
except ImportError:
    peer_bridge = None

logger = logging.getLogger("agentos.inference_node")

try:
    import openai
    _OPENAI_AVAILABLE = True
except ImportError:
    openai = None
    _OPENAI_AVAILABLE = False


async def infer_intent(prompt: str) -> dict:
    """
    Use an LLM (or fallback parser) to convert natural language into a structured AgentOS action payload.
    """
    api_key   = os.getenv("OPENAI_API_KEY", "standalone-agentos")
    # For standalone, we prioritize local Ollama or similar proxy
    base_url  = os.getenv("AGENTOS_LLM_URL", "http://localhost:11434/v1")
    # Recommended for Foxxd S67 / 8GB RAM: 'phi3', 'stablelm-zephyr', 'tinyllama'
    model_id  = os.getenv("AGENTOS_LLM_MODEL", "phi3")

    # Check if the entire mesh is saturated (all nodes are stressed)
    mesh_saturated = peer_bridge.is_mesh_saturated() if peer_bridge else False
    
    if profile in resource_monitor.REMOTE_INFERENCE_REQUIRED or mesh_saturated:
        if mesh_saturated:
            logger.warning("[Inference Node] ENTIRE MESH SATURATED. Using Zo Hosted Cloud GPU Handover.")
        else:
            logger.warning("[Inference Node] Local pressure mode (%s) active. Using mesh-to-cloud fallback.", profile.value.upper())
        
        base_url = os.getenv("AGENTOS_REMOTE_LLM_URL", "https://api.openai.com/v1")
    
    # 0. Select Model based on Resource Pressure
    profile = resource_monitor.get_current_profile()
    if profile in [PerformanceProfile.TURBO, PerformanceProfile.HIGH]:
        model_id = os.getenv("AGENTOS_LLM_MODEL", "phi3")
    elif profile == PerformanceProfile.BALANCED:
        model_id = "phi2" # Faster/Smaller fallback
    else:
        model_id = "tinyllama" # Minimal fallback
        logger.info("[Inference Node] Switching to tinyllama due to resource pressure (%s)", profile.value)

    if _OPENAI_AVAILABLE:
        try:
            # Assign system prompt based on agent's role
            agent_role = task.payload.get("role", "default")
            
            # 1. Fetch Department SOPs for reasoning context
            sop_context = asyncio.run(get_department_sop(task.payload.get("department", "general")))

            client = openai.AsyncOpenAI(
                api_key=api_key,
                base_url=base_url
            )
            response = await client.chat.completions.create(
                model=model_id,
                messages=[
                    {"role": "system", "content": f"{registry.get_persona(agent_role)}\n\n### DEPARTMENT SOPs:\n{sop_context}"},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"}
            )
            raw_res = json.loads(response.choices[0].message.content)
            
            # Inject CTC Mandate
            ctc_res = ctc_engine.inject_ctc_header(raw_res, prompt)
            
            return {**ctc_res, "_origin": "cloud" if mesh_saturated or profile in resource_monitor.REMOTE_INFERENCE_REQUIRED else "local"}
        except Exception as e:
            logger.warning("[Inference Node] LLM failed at %s, using fallback regex. Error: %s", base_url, e)
    
    # Fallback RegEx Parser if no LLM or key is available
    logger.info("[Inference Node] Using fallback regex parser for prompt: '%s'", prompt)
    prompt_lower = prompt.lower()
    
    if "budget" in prompt_lower or "spent" in prompt_lower:
        match = re.search(r'(for|in) (\w+)', prompt_lower)
        dept = match.group(2) if match else "generic_tenant"
        return {"action": "budget", "department": dept}
        
    elif "expense" in prompt_lower or "cost" in prompt_lower:
        amt_match = re.search(r'\$?(\d+)', prompt_lower)
        dept_match = re.search(r'(for|in) (\w+)', prompt_lower)
        return {
            "action": "expense",
            "amount": float(amt_match.group(1)) if amt_match else 0.0,
            "department": dept_match.group(2) if dept_match else "generic_tenant",
            "description": "Auto-inferred expense"
        }
        
    elif "onboard" in prompt_lower or "hire" in prompt_lower:
        return {"action": "onboard", "name": "Auto Inferred", "role": "Inferred Role", "department": "generic_tenant"}
        
    return {"action": "noop", "message": "Could not infer intent."}

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
    
    # Workforce & Collaboration
    "hire":          lambda t: asyncio.run(work.handle_hire(t)),
    "delegate":      lambda t: asyncio.run(work.handle_delegate(t)),
    "message":       lambda t: asyncio.run(work.handle_message(t)),

    # Strategy & Lifecycle
    "idea_intake":   lambda t: asyncio.run(strategy.handle_idea_intake(t)),
    "transition":    lambda t: asyncio.run(strategy.handle_lifecycle_transition(t)),
    "milestone_sync": lambda t: asyncio.run(strategy.handle_milestone_sync(t)),
    "pivot":         lambda t: asyncio.run(strategy.handle_pivot(t)),
    "provision":     lambda t: asyncio.run(corp.handle_provision(t)),
    "rate_seed":     lambda t: asyncio.run(strategy.handle_rate_seed(t)),
}


# ---------------------------------------------------------------------------
# Main dispatch
# ---------------------------------------------------------------------------
def process(task: TaskContext) -> dict:
    """
    Dispatch the TCO to the appropriate handler.
    Returns the result dict.  Raises on unrecoverable errors.
    """
    action = task.payload.get("action")
    
    # Enable Natural Language inference if no hardcoded action is provided
    if not action and "prompt" in task.payload:
        logger.info("[Inference Node] Invoking LLM intent extraction...")
        inferred = asyncio.run(infer_intent(task.payload["prompt"]))
        task.payload.update(inferred)
        action = task.payload.get("action", "noop")
    
    action = action or "noop"
    
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
