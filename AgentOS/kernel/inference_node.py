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
from AgentOS.core import config, db, models, persona, security
from AgentOS.core.db import RQE
from AgentOS.core.models import TaskContext
from AgentOS.kernel.registry import registry
import AgentOS.logic.strategy as strategy
import AgentOS.logic.corporate as corporate

import re
import os
import psutil # Add to requirements.txt if not present
import resource_monitor
from resource_monitor import PerformanceProfile
import ctc_engine

# Link to peer bridge for mesh-wide status
try:
    from AgentOS.sync_engine import peer_bridge
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
                    {"role": "system", "content": f"{persona.get_persona(agent_role)}\n\n### DEPARTMENT SOPs:\n{sop_context}"},
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
# Main dispatch
# ---------------------------------------------------------------------------

async def process(task: TaskContext | dict) -> dict:
    """
    Main dispatch entry point for TCOs.
    Returns the result dict.  Raises on unrecoverable errors.
    """
    # Auto-convert dict to Pydantic/Dataclass if needed
    if isinstance(task, dict):
        task = TaskContext(
            task_id=task.get("task_id", "AUTO"),
            tenant=task.get("tenant", "tenant_zero"),
            payload=task.get("payload", {})
        )

    action = task.payload.get("action")
    
    # Enable Natural Language inference if no hardcoded action is provided
    if not action and "prompt" in task.payload:
        logger.info("[Inference Node] Invoking LLM intent extraction...")
        inferred = await infer_intent(task.payload["prompt"])
        task.payload.update(inferred)
        action = task.payload.get("action", "noop")
    
    action = action or "noop"
    
    handler = registry.get_handler(action)
    if not handler:
        # Check system defaults
        if action == "ping":
            return {"status": "ok", "msg": "pong"}
        
        logger.error("[Inference] No handler registered for action: %s", action)
        return {"status": "error", "message": f"Action '{action}' not recognized."}

    t0 = time.perf_counter()
    try:
        # Silicon-speed ETA injection (CTC Mandate)
        ctc = ctc_engine.calculate_ctc(100) # Baseline prompt len
        eta = ctc["eta_human"]
        
        result = await handler(task)
        elapsed_ms = (time.perf_counter() - t0) * 1e3
        
        final_res = {
            **result, 
            "eta": eta,
            "_elapsed_ms": round(elapsed_ms, 3)
        }
        
        logger.info("Task %s [%s] completed in %.2f ms.", task.task_id, action, elapsed_ms)
        return final_res

    except Exception as exc:
        logger.exception("Task %s failed: %s", task.task_id, exc)
        return {"status": "error", "message": str(exc)}


def _persist(task: TaskContext, dest_dir: Path) -> None:
    dest_dir.mkdir(parents=True, exist_ok=True)
    path = dest_dir / f"{task.task_id}.json"
    path.write_text(task.to_json())
