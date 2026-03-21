"""
test_inference_route.py — Validate Natural Language Intent Routing
"""

import sys
import json
from pathlib import Path

root = Path(__file__).parent.parent.parent
sys.path.append(str(root))

from AgentOS.kernel.task_context import TaskContext
from AgentOS.kernel import inference_node

def test_inference_node():
    print("🧠 Testing Inference Node NLP Routing...\n")
    
    # Send a RAW string prompt instead of a JSON payload
    prompt_payload = {
        "prompt": "Hey Ops, we need a budget check for generic_tenant please."
    }
    
    task = TaskContext(
        task_id="nlp_test_101",
        tenant="tenant_zero",
        priority=0,
        payload=prompt_payload,
        created_at="2026-03-21T00:00:00Z"
    )
    
    # Process the task
    print(f"[Input] {prompt_payload['prompt']}")
    result = inference_node.process(task)
    
    print("\n[Output Result]")
    print(json.dumps(result, indent=2))
    
    # Assertions to ensure it actually inferred "action": "budget" and executed OpsAgent
    assert task.payload.get("action") == "budget"
    assert result.get("department") == "generic_tenant"
    assert "total_spent" in result
    print("\n✓ Natural language intent successfully routed to Agent OS handlers.")

if __name__ == "__main__":
    test_inference_node()
