#!/usr/bin/env python3
"""
run_funnel_scenarios.py — Execute and compare Irrig8 ROI scenarios.
"""
import sys
from pathlib import Path

# Add project root to sys.path
root = Path(__file__).parent.parent.parent.parent.parent
sys.path.append(str(root))

from AgentOS.tenants.irrig8.logic.pricing_funnel import PricingFunnel

def main():
    print("🌽 Irrig8 ROI Precision Comparison")
    print("-----------------------------------")
    funnel = PricingFunnel(acre_count=5000, crop_yield_value=450)
    
    # Satellite Baseline (10m - 30m resolution)
    print("Base Scenario: Sparse Satellite Data")
    sat_roi = funnel.calculate_roi_boost(moisture_precision=0.4, ndvi_precision=0.5)
    print(f"  Annual Savings: ${sat_roi['annual_savings_usd']:,.2f}")
    print(f"  Efficiency Rating: {sat_roi['efficiency_rating']}")
    
    # AgentOS 1m Sensor Grid
    print("\nTarget Scenario: AgentOS 1m Sensor Grid")
    grid_roi = funnel.calculate_roi_boost(moisture_precision=0.95, ndvi_precision=0.90)
    print(f"  Annual Savings: ${grid_roi['annual_savings_usd']:,.2f}")
    print(f"  Efficiency Rating: {grid_roi['efficiency_rating']}")
    print(f"  Pop Multiplier: {grid_roi['resolution_pop_multiplier']}x")
    
    print("\n✓ Funnel Scenarios Executed Successfully.")

if __name__ == "__main__":
    main()
