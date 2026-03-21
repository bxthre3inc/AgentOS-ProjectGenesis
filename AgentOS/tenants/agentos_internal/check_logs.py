#!/usr/bin/env python3
"""
check_logs.py — Autonomous Log Analysis for Tenant Zero.

Examines the kernel logs for recursive self-optimization opportunities.
"""

import re
import sys
from pathlib import Path

# Add project root to sys.path
root = Path(__file__).parent.parent.parent.parent
sys.path.append(str(root))

LOGS_DIR = root / "AgentOS" / "tenants" / "agentos_internal" / "logs"

def analyze_logs():
    print("🔍 Tenant Zero: Autonomous Log Analysis initiated.")
    if not LOGS_DIR.exists():
        print("No logs directory found.")
        return

    optimization_opportunities = []
    
    # Simple regex to find TCO hand-off timings
    tco_pattern = re.compile(r"Best observed: (\d+(?:\.\d+)?) µs/op")
    
    for log_file in LOGS_DIR.glob("*.log"):
        with open(log_file, "r") as f:
            content = f.read()
            
            # Check for TCO Hand-off timings
            match = tco_pattern.search(content)
            if match:
                timing = float(match.group(1))
                print(f"[{log_file.name}] Detected TCO hand-off speed: {timing} µs/op")
                if timing > 50.0:
                    optimization_opportunities.append(
                        f"TCO hand-off is slow ({timing} µs/op). Recommend optimizing core IO loops."
                    )
                else:
                    print("  ✓ TCO hand-off is within 50 µs SLA.")

    print("\n--- Summary ---")
    if optimization_opportunities:
        print("⚠️ Optimization Opportunities Found:")
        for opp in optimization_opportunities:
            print(f"  - {opp}")
    else:
        print("✨ System Optimal: No immediate self-optimization required.")

if __name__ == "__main__":
    analyze_logs()
