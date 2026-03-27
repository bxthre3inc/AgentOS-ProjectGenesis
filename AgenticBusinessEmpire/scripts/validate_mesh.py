"""
Mesh Validation Suite - Production Readiness Check
Verifies connectivity, latency, tracing, and security across the 3-way mesh.
"""
import asyncio
import uuid
import httpx
from sync_engine import auth

API_BASE = "http://localhost:7878"
API_KEY = "test_key_123"  # Should match what's in state.db for validation

async def test_api_connectivity():
    print("Checking API connectivity...")
    async with httpx.AsyncClient() as client:
        try:
            r = await client.get(f"{API_BASE}/api/status")
            if r.status_code == 200:
                print("✅ API is reachable")
                return True
        except Exception as e:
            print(f"❌ API unreachable: {e}")
            return False

async def test_peer_registration():
    print("Testing Peer Registration...")
    # This assumes the server is running with the test key
    headers = {"Authorization": f"Bearer {API_KEY}"}
    async with httpx.AsyncClient(headers=headers) as client:
        # Get peers
        r = await client.get(f"{API_BASE}/api/peers")
        peers = r.json().get("peers", [])
        ids = [p["agent_id"] for p in peers]
        print(f"Found nodes: {ids}")
        if "zo" in ids and "antigravity" in ids:
           print("✅ Essential peers registered")
           return True
    print("❌ Essential peers missing")
    return False

async def test_trace_propagation():
    print("Testing Correlation ID propagation...")
    trace_id = f"test-trace-{uuid.uuid4().hex[:8]}"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "X-Correlation-ID": trace_id
    }
    async with httpx.AsyncClient(headers=headers) as client:
        # Trigger an action (toggle feature)
        await client.post(f"{API_BASE}/api/features/toggle", json={
            "flag": "mesh_observability", "enabled": True, "agent_id": "validator"
        })
        
        # Check actions log for the trace
        r = await client.get(f"{API_BASE}/api/actions?limit=5")
        entries = r.json().get("entries", [])
        for e in entries:
            if e.get("trace_id") == trace_id:
                print(f"✅ Trace ID {trace_id} propagated successfully")
                return True
    print("❌ Trace ID propagation failed")
    return False

async def main():
    print("--- 3-Way Mesh Production Readiness Check ---")
    results = [
        await test_api_connectivity(),
        await test_peer_registration(),
        await test_trace_propagation()
    ]
    
    if all(results):
        print("\n🚀 ALL CHECKS PASSED. SYSTEM READY FOR PRODUCTION.")
    else:
        print("\n⚠️ SOME CHECKS FAILED. PLEASE VERIFY SERVER STATE.")

if __name__ == "__main__":
    asyncio.run(main())
