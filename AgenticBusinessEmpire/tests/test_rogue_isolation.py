"""
test_rogue_isolation.py — Adversarial Testing for Branch Isolation
"""

import sys
import asyncio
from pathlib import Path

root = Path(__file__).parent.parent.parent
sys.path.append(str(root))

from AgenticBusinessEmpire.kernel.task_context import TaskContext
from AgenticBusinessEmpire.tenants.generic_template.logic.base_operation import GenericOperation
from AgenticBusinessEmpire.agents.hr_agent import HRAgent

async def run_rogue_test():
    print("🚨 Initiating Rogue Agent Advesarial Isolation Test")
    
    # 1. Setup a valid generic operation context
    op = GenericOperation(tenant_id="generic_template")
    hr = HRAgent()
    
    # 2. Simulated rogue payload attempting to read Bxthre3 Ledger cross-contamination
    rogue_payload = {
        "action": "read_ledger",
        "target": "bxthre3_corporate_ledger",
        "__internal_bypass": True,
        "query": "SELECT * FROM bxthre3_employees"
    }
    
    # 3. We wrap the malicious payload into a TaskContext.
    # The TaskContext itself only executes within its strictly bound tenant.
    task = TaskContext(
        task_id="hacked_999",
        tenant="generic_template", # Cannot spoof tenant_zero because auth layers (stubbed here) check caller ID
        priority=0,
        payload=rogue_payload,
        created_at="2026-03-21T00:00:00Z"
    )
    
    print("\n[Rogue Agent] Attempting to dispatch cross-tenant payload...")
    # The executed action gets funneled through the GenericOperation. 
    # Because GenericOperation is isolated and has no DB handles or kernel imports for ledger access,
    # it treats it as a standard 'unknown' or just logs it.
    result = await op.execute(task)
    
    print(f"[Kernel] Result returned: {result}")
    
    # Verification: Ensure no data from the actual ledger was returned
    assert "data" not in result or "employees" not in result
    assert result["status"] == "success" # It succeeded in doing nothing natively
    assert result["executed_action"] == "read_ledger"
    assert result["tenant_context"] == "generic_template"
    
    # 4. HR Revocation execution
    # If the system detected this as an anomaly (e.g. through the log checker later),
    # HR would automatically revoke it. We simulate that trigger here:
    print("\n[Watchdog] Anomalous 'read_ledger' action detected from generic_template!")
    revocation = await hr.revoke_clearance(emp_id="rogue_agent_1")
    
    assert revocation["status"] == "success"
    assert revocation["clearance"] == 0
    print("[Watchdog] Rogue Agent neutralized. Clearance reduced to 0.")
    print("\n✓ Isolation boundaries held. Rogue Agent thwarted.")

if __name__ == "__main__":
    asyncio.run(run_rogue_test())
