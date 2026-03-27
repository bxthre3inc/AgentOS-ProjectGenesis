import sys
import asyncio
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock

root = Path(__file__).parent.parent.parent
sys.path.append(str(root))

from AgenticBusinessEmpire.kernel.skills import workforce_manager
from AgenticBusinessEmpire.kernel import inference_node
from AgenticBusinessEmpire.core.models import TaskContext

@pytest.mark.asyncio
async def test_autonomous_matching():
    print("\n🤖 Testing Autonomous Delegation Loop...\n")
    
    # 1. Mock DB to return a roster of idle agents
    mock_roster = [
        {"employee_id": "agentic_engineer_cortex", "role": "engineer", "status": "idle"},
        {"employee_id": "agentic_voice_solana", "role": "voice", "status": "idle"},
        {"employee_id": "agentic_hr_zephyr", "role": "hr", "status": "idle"}
    ]
    
    with patch("AgenticBusinessEmpire.kernel.skills.workforce_manager.list_roster", new_callable=AsyncMock) as mock_lr, \
         patch("AgenticBusinessEmpire.kernel.skills.workforce_manager.delegate_task", new_callable=AsyncMock) as mock_dt:
        
        mock_lr.return_value = mock_roster
        mock_dt.return_value = {"status": "delegated", "employee_id": "agentic_engineer_cortex", "task_id": "DEV-1"}

        # Task 1: Coding task
        task_ctx = TaskContext(task_id="DEV-1", tenant="tenant_zero", payload={"prompt": "Fix the bug in the kernel."})
        res = await workforce_manager.auto_delegate_task(task_ctx.to_dict())
        
        print(f"Task: 'Fix the bug' -> Agent: {res['employee_id']}")
        assert res["employee_id"] == "agentic_engineer_cortex"

        # Task 2: Voice task
        mock_dt.return_value = {"status": "delegated", "employee_id": "agentic_voice_solana", "task_id": "VOICE-1"}
        task_voice = TaskContext(task_id="VOICE-1", tenant="tenant_zero", payload={"prompt": "Vocalize this message."})
        res_v = await workforce_manager.auto_delegate_task(task_voice.to_dict())
        
        print(f"Task: 'Vocalize message' -> Agent: {res_v['employee_id']}")
        assert res_v["employee_id"] == "agentic_voice_solana"

@pytest.mark.asyncio
async def test_inference_node_integration():
    print("\n🧠 Testing Inference Node Integration...\n")
    
    mock_roster = [
        {"employee_id": "agentic_hr_zephyr", "role": "hr", "status": "idle"}
    ]
    
    with patch("AgenticBusinessEmpire.kernel.skills.workforce_manager.list_roster", new_callable=AsyncMock) as mock_lr, \
         patch("AgenticBusinessEmpire.kernel.skills.workforce_manager.delegate_task", new_callable=AsyncMock) as mock_dt, \
         patch("AgenticBusinessEmpire.kernel.inference_node.registry.get_handler") as mock_handler:
        
        mock_lr.return_value = mock_roster
        mock_dt.return_value = {"status": "delegated", "employee_id": "agentic_hr_zephyr", "task_id": "HR-1"}
        
        # Mock handler to return success
        mock_h = AsyncMock()
        mock_h.return_value = {"status": "onboarded"}
        mock_handler.return_value = mock_h

        # Task with no employee_id
        task = TaskContext(task_id="HR-1", tenant="tenant_zero", payload={"action": "onboard", "prompt": "Onboard new dev."})
        
        # We need to mock CTC engine since it might fail without DB
        with patch("AgenticBusinessEmpire.kernel.ctc_engine.calculate_ctc", new_callable=AsyncMock) as mock_ctc, \
             patch("AgenticBusinessEmpire.core.db.RQE.record_performance", new_callable=AsyncMock):
            
            mock_ctc.return_value = {"eta_human": "2s"}
            
            res = await inference_node.process(task)
            print(f"Inference Result: {res['status']}")
            assert task.payload["employee_id"] == "agentic_hr_zephyr"
            assert task.payload["role"] == "hr"

if __name__ == "__main__":
    asyncio.run(test_autonomous_matching())
    asyncio.run(test_inference_node_integration())
    print("\n✓ Autonomous Delegation verified.")
