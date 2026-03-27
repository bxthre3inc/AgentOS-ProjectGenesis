"""
benchmark_rqe.py — RQE Performance Validation
"""
import asyncio
import sys
import time
import random
from pathlib import Path

# Add project root to sys.path
root = Path(__file__).parent.parent.parent.parent
sys.path.append(str(root))

from AgenticBusinessEmpire.core.db import RQE

async def run_benchmark(num_queries: int = 100):
    print(f"🚀 Starting RQE Benchmark: {num_queries} spatial queries...")
    rqe = RQE(pool=None) # Using stub for automated CI benchmark
    
    # Melbourne bounding box approx
    lat_range = (-37.9, -37.7)
    lon_range = (144.8, 145.1)
    layers = ["ndvi", "elevation_m", "soil_moisture_pct"]
    tenant = "subsidiary_beta"
    
    latencies = []
    
    for i in range(num_queries):
        lat = random.uniform(*lat_range)
        lon = random.uniform(*lon_range)
        
        t0 = time.perf_counter()
        await rqe.query(lat, lon, layers, tenant)
        elapsed = (time.perf_counter() - t0) * 1000
        latencies.append(elapsed)
        
        if (i+1) % 20 == 0:
            print(f"  Processed {i+1}/{num_queries}...")
            
    avg = sum(latencies) / len(latencies)
    p95 = sorted(latencies)[int(num_queries * 0.95) - 1]
    
    print("\nBenchmark Results:")
    print(f"  Average Latency: {avg:.3f} ms")
    print(f"  P95 Latency:     {p95:.3f} ms")
    print(f"  SLA Compliance:  {'✓ PASS' if p95 <= 100 else '✗ FAIL'}")

if __name__ == "__main__":
    asyncio.run(run_benchmark())
