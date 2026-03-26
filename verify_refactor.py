import asyncio
import sys
import os
import json

# Add project root to path
sys.path.append(os.getcwd())

from AgentOS.core import config, db, models, security
from AgentOS.kernel import registry, inference_node

async def test_integration():
    print("--- Phase 3 Integrated Verification ---")
    
    # 1. Verify Config
    print(f"Profile: {'MOBILE' if config.IS_MOBILE else 'SERVER'}")
    print(f"Master DB: {config.MASTER_DB_PATH}")
    assert "agentos.db" in config.MASTER_DB_PATH

    # 2. Verify Models (Pydantic)
    tco = models.TaskContext(
        task_id="VERIFY-01",
        tenant="tenant_zero",
        payload={"action": "idea_intake", "title": "Modular AI", "description": "Test"}
    )
    print(f"Pydantic Validation: OK ({tco.task_id})")

    # 3. Verify RQE & Security
    secret = "TopSecret123"
    encrypted = security.SecureData.encrypt(secret)
    decrypted = security.SecureData.decrypt(encrypted)
    assert secret == decrypted
    print("Encryption/Decryption: OK")

    # 4. Verify Handler Registry & Dispatch
    # We manually register a test handler
    @registry.registry.register("test_verify")
    async def handle_test(task):
        return {"status": "ok", "message": "Handler Registry Connected"}

    # Pass dict to process() for auto-conversion
    result = await inference_node.process({
        "task_id": "VERIFY-02",
        "tenant": "tenant_zero",
        "payload": {"action": "test_verify"}
    })
    
    print(f"Modular Dispatch Result: {result.get('status')}")
    if result.get("status") == "error":
        print(f"Error Detail: {result.get('message')}")
    assert result["status"] == "ok"
    assert "eta" in result
    print("Zero-Latency Dispatch (CTC): OK")
    
    print("\n✅ CORE INTEGRATION SUCCESSFUL")

if __name__ == "__main__":
    asyncio.run(test_integration())
