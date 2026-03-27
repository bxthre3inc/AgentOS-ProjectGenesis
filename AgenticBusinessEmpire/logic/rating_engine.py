"""
rating_engine.py — AgenticBusinessEmpire Fit-to-Empire Rating Engine
"""
import json
import logging
import sys
import os
from AgenticBusinessEmpire.kernel import ctc_engine

logger = logging.getLogger("agenticbusinessempire.logic.rating_engine")

from AgenticBusinessEmpire.kernel import inference_node

async def audit_seed(seed_id: str, title: str, description: str) -> dict:
    """
    Perform a live strategic audit via the Inference Node.
    Calls the Nova + Lyra evaluation board.
    """
    logger.info("[Rating Engine] Requesting live audit for seed: %s", seed_id)
    
    # Dispatch to the specialized board
    result = await inference_node.process({
        "task_id": f"AUDIT-{seed_id}",
        "tenant": "tenant_zero",
        "payload": {
            "action": "evaluate_seed",
            "seed_id": seed_id,
            "title": title,
            "description": description
        }
    })
    
    return result
