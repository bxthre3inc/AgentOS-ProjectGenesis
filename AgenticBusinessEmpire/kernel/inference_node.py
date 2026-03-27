"""
inference_node.py — AgenticBusinessEmpire Inference Node

The Inference Node processes a single Task Context Object (TCO):
  1. Accepts the TCO.
  2. Routes it to the correct handler by inspecting payload['action'].
  3. Writes the result back to runtime/tasks/completed/<task_id>.json.
  4. If an exception occurs, writes to runtime/tasks/failed/<task_id>.json.

All reasoning logic is intentionally kept in separate handler modules under
AgenticBusinessEmpire/kernel/handlers/ to keep this file as a pure dispatcher.
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
_AGENTIC_BUSINESS_EMPIRE_DIR = _KERNEL_DIR.parent
_RUNTIME_COMPLETED = _AGENTIC_BUSINESS_EMPIRE_DIR / "runtime" / "tasks" / "completed"
_RUNTIME_FAILED    = _AGENTIC_BUSINESS_EMPIRE_DIR / "runtime" / "tasks" / "failed"

sys.path.insert(0, str(_KERNEL_DIR))
from AgenticBusinessEmpire.core import config, db, models, persona, security
from AgenticBusinessEmpire.core.db import RQE
from AgenticBusinessEmpire.core.models import TaskContext
from AgenticBusinessEmpire.kernel.registry import registry
import AgenticBusinessEmpire.logic.strategy as strategy
import AgenticBusinessEmpire.logic.corporate as corporate
import AgenticBusinessEmpire.logic.evaluation as evaluation
import AgenticBusinessEmpire.kernel.skills.ecosystem_skills as ecosystem_skills

import re
import os
import random
import psutil # Add to requirements.txt if not present
import resource_monitor
from resource_monitor import PerformanceProfile
import ctc_engine

# Link to peer bridge for mesh-wide status
try:
    from AgenticBusinessEmpire.sync_engine import peer_bridge
except ImportError:
    peer_bridge = None

logger = logging.getLogger("agenticbusinessempire.inference_node")

import httpx

async def get_department_sop(department: str) -> str:
    """
    Fetch the Standard Operating Procedure (SOP) for a given department.
    Backed by shared/department_sops.json.
    """
    import json
    from AgenticBusinessEmpire.core import config
    
    sop_path = os.path.join(config.SHARED_DIR, "department_sops.json")
    try:
        with open(sop_path, "r") as f:
            sops = json.load(f)
        return sops.get(department.lower(), sops.get("general", "Follow standard protocols."))
    except Exception as e:
        logger.error("[Inference Node] Failed to load SOPs from %s: %s", sop_path, e)
        return "Follow general conglomerate-scale automation protocols."

async def infer_intent(task: TaskContext) -> dict:
    """
    Use a local LLM to convert natural language into a structured AgenticBusinessEmpire action payload.
    Supports multimodal inputs if an image is provided in the task payload.
    """
    prompt = task.payload.get("prompt", "")
    image_data = task.payload.get("image") # Base64 or URL for multimodal
    
    base_url = config.LLM_BASE_URL
    
    # Select model based on task type (Multimodal vs Text/Tools)
    if image_data:
        model_id = config.MULTIMODAL_MODEL
    else:
        model_id = config.DEFAULT_MODEL

    # Assign system prompt based on agent's role
    agent_role = task.payload.get("role", "default")
    sop_context = await get_department_sop(task.payload.get("department", "general"))
    
    system_prompt = f"{persona.get_persona(agent_role)}\n\n### DEPARTMENT SOPs:\n{sop_context}"
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt}
    ]

    # Add image if multimodal
    if image_data and "llava" in model_id.lower() or "moondream" in model_id.lower():
        # Adjusting for Ollama/OpenAI-compatible multimodal format
        messages[-1]["content"] = [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": image_data}}
        ]

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{base_url}/chat/completions",
                json={
                    "model": model_id,
                    "messages": messages,
                    "response_format": {"type": "json_object"} if not image_data else None,
                    "temperature": 0.0
                }
            )
            resp.raise_for_status()
            res_json = resp.json()
            content = res_json["choices"][0]["message"]["content"]
            
            # Ollama sometimes returns raw JSON even if format is requested
            raw_res = json.loads(content) if isinstance(content, str) else content
            
            # Inject CTC Mandate
            ctc_res = await ctc_engine.inject_ctc_header(raw_res, prompt, action=task.payload.get("action", "default"))
            
            return {**ctc_res, "_origin": "local", "_model": model_id}
            
    except Exception as e:
        logger.warning("[Inference Node] Local LLM failed at %s. Error: %s", base_url, e)
        return _fallback_regex(prompt)

def _fallback_regex(prompt: str) -> dict:
    # Fallback RegEx Parser if no LLM is available
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
        
    return {"action": "noop", "_fallback": True}

# ---------------------------------------------------------------------------
# Main dispatch
# ---------------------------------------------------------------------------

async def process(task: TaskContext | dict) -> dict:
    """
    Main dispatch entry point for TCOs.
    Returns the result dict.  Raises on unrecoverable errors.
    """
    t0 = time.perf_counter()
    
    # Auto-convert dict to Pydantic/Dataclass if needed
    if isinstance(task, dict):
        task = TaskContext(
            task_id=task.get("task_id", "AUTO"),
            tenant=task.get("tenant", "tenant_zero"),
            payload=task.get("payload", {})
        )

    # Advanced Decentralized Load Balancing
    profile = resource_monitor.get_current_profile()
    image_task = "image" in task.payload
    
    # Probabilistic Shedding Thresholds
    shed_chance = 0.0
    if profile == PerformanceProfile.CRITICAL:
        shed_chance = 1.0
    elif profile == PerformanceProfile.LOW:
        shed_chance = 0.5
    elif profile == PerformanceProfile.BALANCED:
        shed_chance = 0.1
        
    # Strategic Routing: Always attempt to offload heavy multimodal tasks to servers if we are on a device
    should_strategic_offload = image_task and not config.IS_SERVER
    
    if (random.random() < shed_chance or should_strategic_offload) and peer_bridge:
        if not task.payload.get("_delegated"):
            # If it's a strategic offload, we specifically request a server
            reqs = {"is_server": True} if should_strategic_offload else None
            
            logger.info("[Inference Node] [%s] %s. Delegating task %s to mesh.", 
                        profile.value.upper(), 
                        "Strategic multimodal routing" if should_strategic_offload else "Probabilistic load shedding",
                        task.task_id)
            
            task.payload["_delegated"] = True
            task_dict = {"task_id": task.task_id, "tenant": task.tenant, "payload": task.payload}
            success = await peer_bridge.delegate_task(task_dict, caller="agenticbusinessempire", requirements=reqs)
            
            if success:
                return {
                    "status": "delegated", 
                    "message": "Task intelligently routed to mesh peer.",
                    "strategy": "multimodal_offload" if should_strategic_offload else "load_shedding"
                }
    
    action = task.payload.get("action")
    
    # Enable Natural Language inference if no hardcoded action is provided
    if not action and "prompt" in task.payload:
        logger.info("[Inference Node] Invoking local LLM intent extraction...")
        inferred = await infer_intent(task)
        task.payload.update(inferred)
        action = task.payload.get("action", "noop")
    
    action = action or "noop"
    
    try:
        # Silicon-speed ETA injection (CTC Mandate)
        ctc = await ctc_engine.calculate_ctc(action, len(str(task.payload)))
        eta = ctc["eta_human"]

        handler = registry.get_handler(action)
        if not handler:
            # Check system defaults
            if action == "ping":
                result = {"status": "ok", "msg": "pong"}
            else:
                logger.error("[Inference] No handler registered for action: %s", action)
                return {"status": "error", "message": f"Action '{action}' not recognized."}
        else:
            result = await handler(task)

        # --- Universal Response Finalization ---
        elapsed_ms = (time.perf_counter() - t0) * 1e3
        
        # Record performance for future CTC calibration
        output_tokens = result.get("_tokens", 512)
        prompt_len = len(str(task.payload))
        await RQE.record_performance(task.task_id, action, prompt_len, output_tokens, elapsed_ms)

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
