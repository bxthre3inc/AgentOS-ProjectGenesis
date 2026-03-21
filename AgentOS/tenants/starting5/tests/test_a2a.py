"""
test_a2a.py — Verification for Starting5 A2A Messaging
"""
import sys
from pathlib import Path

# Add project root to sys.path
root = Path(__file__).parent.parent.parent.parent.parent
sys.path.append(str(root))

from AgentOS.tenants.starting5.src.roster_controller import create_default_bus

def test_a2a_flow():
    print("Testing Starting5 A2A Messaging...")
    bus, pg, c, sg, sf, pf = create_default_bus()
    
    goal = "Calculate ROI for 5000 acres of corn."
    print(f"Dispatching goal: {goal}")
    replies = pg.dispatch(goal)
    
    for r in replies:
        print(f"Reply from {r.from_pos}: {r.payload.get('summary')}")
        if r.from_pos == "C":
            assert r.payload.get("isolation_enforced") == True
            print("✓ Financial isolation verified")
            
    print("✓ A2A flow test passed")

if __name__ == "__main__":
    test_a2a_flow()
