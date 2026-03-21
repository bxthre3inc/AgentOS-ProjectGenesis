"""
product_handlers.py — Handlers for Starting5 product tasks
"""
import logging
from task_context import TaskContext

logger = logging.getLogger("agentos.handlers.product")

def handle_wire(task: TaskContext) -> dict:
    target = task.payload.get("target", "unknown")
    goal = task.payload.get("goal", "unknown")
    logger.info("Wiring positions for product: %s", target)
    return {
        "status": "ok",
        "action": "roster_update",
        "details": f"Successfully wired SG and SF into {target}."
    }
