"""
test_generic.py — Ensure Generic Tenant complies with isolation
"""

import sys
import asyncio
from pathlib import Path

root = Path(__file__).parent.parent.parent.parent.parent
sys.path.append(str(root))

from AgenticBusinessEmpire.kernel.task_context import TaskContext
from AgenticBusinessEmpire.tenants.generic_template.logic.base_operation import GenericOperation

async def run_tests():
    print("🧪 Testing Generic Tenant Template")
    op = GenericOperation(tenant_id="template_test_1")
    
    # Simulate a kernel-issued task
    payload = {"action": "initialize_grid", "target": "sector_7G"}
    task = TaskContext(
        task_id="test_001",
        tenant="generic_template",
        priority=1,
        created_at="2026-03-21T00:00:00Z",
        payload=payload
    )
    
    result = await op.execute(task)
    
    print(f"Result: {result}")
    assert result["status"] == "success"
    assert result["tenant_context"] == "template_test_1"
    assert result["executed_action"] == "initialize_grid"
    
    print("✓ Generic Tenant execution isolated and successful.")

if __name__ == "__main__":
    asyncio.run(run_tests())
