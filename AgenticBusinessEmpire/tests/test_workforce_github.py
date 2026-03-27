import sys
import asyncio
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock

root = Path(__file__).parent.parent.parent
sys.path.append(str(root))

from AgenticBusinessEmpire.kernel.skills import workforce_manager
from AgenticBusinessEmpire.kernel.skills import github_skill
from AgenticBusinessEmpire.core.models import TaskContext

@pytest.mark.asyncio
async def test_workforce_delegation():
    # Mock DB
    with patch("AgenticBusinessEmpire.core.db.RQE.execute", new_callable=AsyncMock) as mock_exec:
        mock_exec.return_value = []
        
        # Test add_employee
        res = await workforce_manager.add_employee("bx3", "dev", "engineer", "agentic", "Cortex")
        assert res["status"] == "ok"
        assert "agentic_engineer_cortex" in res["employee_id"]
        
        # Test delegate_task
        task_ctx = {"task_id": "TASK-123"}
        res = await workforce_manager.delegate_task("agentic_engineer_cortex", task_ctx)
        assert res["status"] == "delegated"
        assert res["task_id"] == "TASK-123"

@pytest.mark.asyncio
async def test_github_list_prs():
    # Mock httpx
    with patch("httpx.AsyncClient.request", new_callable=AsyncMock) as mock_req:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [{"number": 1, "title": "Test PR"}]
        mock_req.return_value = mock_resp
        
        # Mock secret for token
        with patch("AgenticBusinessEmpire.core.config.get_secret", return_value="mock_token"):
            # Re-init skill to pick up mock token
            skill = github_skill.GitHubSkill()
            res = await skill.list_prs("owner/repo")
            assert len(res) == 1
            assert res[0]["title"] == "Test PR"

@pytest.mark.asyncio
async def test_github_review_pr():
    # Mock inference node and httpx
    with patch("AgenticBusinessEmpire.kernel.inference_node.process", new_callable=AsyncMock) as mock_inf:
        mock_inf.return_value = {"tasks": ["Review code", "Check tests"]}
        
        with patch("httpx.AsyncClient.request", new_callable=AsyncMock) as mock_req:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"number": 1, "title": "Test PR", "diff_url": "http://diff"}
            mock_req.return_value = mock_resp
            
            with patch("AgenticBusinessEmpire.core.config.get_secret", return_value="mock_token"):
                skill = github_skill.GitHubSkill()
                res = await skill.review_pr("owner/repo", 1)
                assert res["status"] == "reviewed"
                assert "tasks" in res["summary"]

if __name__ == "__main__":
    asyncio.run(test_workforce_delegation())
    asyncio.run(test_github_list_prs())
    asyncio.run(test_github_review_pr())
    print("\n✓ Verification tests passed.")
