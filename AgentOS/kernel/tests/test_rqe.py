"""
test_rqe.py — Verification for RQE Spatial Logic
"""
import asyncio
import sys
from pathlib import Path

# Add project root to sys.path
root = Path(__file__).parent.parent.parent.parent
sys.path.append(str(root))

from AgentOS.kernel.rqe import RQE

async def test_spatial_query():
    print("Testing RQE Spatial Query (Stub Mode)...")
    rqe = RQE(pool=None) # Use stub
    
    lat, lon = -37.8136, 144.9631
    layers = ["ndvi", "elevation_m"]
    tenant = "subsidiary_beta"
    
    result = await rqe.query(lat, lon, layers, tenant)
    print(f"Result for ({lat}, {lon}):")
    print(f"  NDVI: {result.data.get('ndvi')}")
    print(f"  Elevation: {result.data.get('elevation_m')}")
    print(f"  Latency: {result.latency_ms:.2f}ms")
    print(f"  Source: {result.source}")
    
    assert "ndvi" in result.data
    assert "elevation_m" in result.data
    print("✓ Test Passed")

if __name__ == "__main__":
    asyncio.run(test_spatial_query())
