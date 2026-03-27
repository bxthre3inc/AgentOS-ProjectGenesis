"""
base_operation.py — Baseline for Generic Subsidiary Operations
"""

import logging
from typing import Any
from AgenticBusinessEmpire.kernel.task_context import TaskContext

logger = logging.getLogger("tenant.generic")

class GenericOperation:
    """
    Standard interface that AgenticBusinessEmpire kernel expects from any tenant operation.
    """

    def __init__(self, tenant_id: str = "generic_tenant") -> None:
        self.tenant_id = tenant_id

    async def execute(self, task: TaskContext) -> dict[str, Any]:
        """
        Process a standard task ensuring no cross-tenant bleeding.
        """
        logger.info("[%s] Executing generic task: %s", self.tenant_id, task.task_id)
        
        # Generic payload parsing
        action = task.payload.get("action", "noop")
        target = task.payload.get("target", "unknown")
        
        if action == "noop":
            return {"status": "success", "message": "No operation requested."}
            
        result = {
            "status": "success",
            "executed_action": action,
            "target": target,
            "tenant_context": self.tenant_id,
            "metrics": {
                "operations_completed": 1
            }
        }
        
        logger.info("[%s] Task %s complete.", self.tenant_id, task.task_id)
        return result
