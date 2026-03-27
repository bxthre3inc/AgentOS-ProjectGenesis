import asyncio
import os
import sys
from pathlib import Path

# Bootstrap paths
_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_ROOT))

from AgenticBusinessEmpire.kernel import voice_service
from AgenticBusinessEmpire.kernel.skills import ecosystem_skills
from AgenticBusinessEmpire.kernel import inference_node
from AgenticBusinessEmpire.core.models import TaskContext

async def test_voice_stack():
    print("🎙️ Testing AgenticBusinessEmpire Voice Stack...\n")
    
    # 1. Test Vocalize (TTS)
    print("[Test] Vocalizing text...")
    res = await voice_service.voice_service.vocalize("Voice enablement complete for AgenticBusinessEmpire.")
    print(f"Result: {res['status']}")
    if res['status'] == 'success':
        print(f"Audio Path: {res['path']}")
    
    # 2. Test Ecosystem Vocalize Handler
    print("\n[Test] Ecosystem Vocalize Handler...")
    task = TaskContext(task_id="VOICE-TEST-1", tenant="tenant_zero", payload={"action": "vocalize", "text": "Hello Bxthre3."})
    res_h = await ecosystem_skills.handle_vocalize(task)
    print(f"Handler Status: {res_h['status']}")

    # 3. Test Voice Call (IVR Stub)
    print("\n[Test] SignalWire IVR Call...")
    task_call = TaskContext(task_id="CALL-TEST-1", tenant="tenant_zero", payload={"action": "voice_call", "to": "+1234567890"})
    res_c = await ecosystem_skills.handle_voice_call(task_call)
    print(f"Call Status: {res_c['status']} for {res_c['to']}")

if __name__ == "__main__":
    asyncio.run(test_voice_stack())
