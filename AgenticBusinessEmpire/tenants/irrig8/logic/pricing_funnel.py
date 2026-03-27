"""
pricing_funnel.py — Irrig8 ROI & Pricing Logic

Calculates the economic value of irrigation optimization based on
soil moisture, NDVI, and evapotranspiration data.
"""

from typing import Any

class PricingFunnel:
    """
    Calculates the 'Resolution Pop' — the increase in ROI by moving
    from 10m satellite data to 1m sensor grid data.
    """

    def __init__(self, acre_count: int, crop_yield_value: float) -> None:
        self.acre_count = acre_count
        self.crop_yield_value = crop_yield_value

    def calculate_roi_boost(self, moisture_precision: float, ndvi_precision: float) -> dict[str, Any]:
        """
        moisture_precision: 0 (poor) to 1.0 (perfect 1m grid)
        ndvi_precision: 0 (poor) to 1.0 (perfect 1m grid)
        """
        # Baseline water waste is approx 15-20% on sparse data
        baseline_waste_pct = 0.18
        
        # Savings from precision
        savings_pct = (moisture_precision * 0.12) + (ndvi_precision * 0.05)
        remaining_waste_pct = max(0, baseline_waste_pct - savings_pct)
        
        annual_savings = self.acre_count * self.crop_yield_value * savings_pct
        
        return {
            "annual_savings_usd": round(annual_savings, 2),
            "waste_reduction_pct": round(savings_pct * 100, 1),
            "efficiency_rating": "Elite" if savings_pct > 0.1 else "Standard",
            "resolution_pop_multiplier": 1.4 if moisture_precision > 0.8 else 1.1
        }

if __name__ == "__main__":
    funnel = PricingFunnel(acre_count=5000, crop_yield_value=450)
    print(funnel.calculate_roi_boost(0.9, 0.85))
