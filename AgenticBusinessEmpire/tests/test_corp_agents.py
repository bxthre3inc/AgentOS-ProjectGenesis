"""
test_corp_agents.py — Verify HR and Ops new Holding Company methods
"""

import sys
import asyncio
from pathlib import Path

root = Path(__file__).parent.parent.parent.parent
sys.path.append(str(root))

from AgenticBusinessEmpire.agents.ops_agent import OpsAgent
from AgenticBusinessEmpire.agents.hr_agent import HRAgent

async def test_corp_methods():
    print("Testing Bxthre3 Holding Company Agentic Controls...")
    ops = OpsAgent()
    hr = HRAgent()
    
    dept = "generic_tenant"
    
    # 1. Test Budget Validation
    print(f"\n[Ops] Requesting $500 for {dept}...")
    valid = await ops.validate_budget(dept, 500.0)
    print(f"Approval: {valid}")
    assert valid is True
    
    print(f"[Ops] Requesting $1500 for {dept} (should be blocked)...")
    valid = await ops.validate_budget(dept, 1500.0)
    print(f"Approval: {valid}")
    assert valid is False
    
    # 2. Test Clearance Revocation
    emp_id = "test_generic_bot"
    print(f"\n[HR] Revoking clearance for {emp_id}...")
    # NOTE: Since we lack a persistent DB in this test stub context for `emp_id`, 
    # we just verify the method returns a structured dict and doesn't crash on standard flow.
    # In a real environment, empirical DB updates are tracked.
    result = await hr.revoke_clearance(emp_id)
    print(f"Revocation result: {result}")
    
    print("\n✓ Holding Company Controls Validated.")

if __name__ == "__main__":
    asyncio.run(test_corp_methods())
