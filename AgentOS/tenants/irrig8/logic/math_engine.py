"""
math_engine.py — Irrig8 Soil Variability & Profiling Math Engine

Provides:
  - Horizontal / Vertical soil variability profiling
  - Resolution tier computation (1m / 10m / 20m / 50m)
  - Moisture-weighted irrigation volume recommendations

All computations are pure Python (no external ML deps) so this module
runs on-hub as well as on the central Zo server.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import NamedTuple


# ---------------------------------------------------------------------------
# Resolution tiers
# ---------------------------------------------------------------------------
class ResolutionTier(Enum):
    """Spatial sampling resolution (metres per cell side)."""
    HIGH   = 1    # 1 m  — precision zone mapping
    MEDIUM = 10   # 10 m — standard field monitoring
    LOW    = 20   # 20 m — coarse field overview
    COARSE = 50   # 50 m — macro / catchment level


TIER_DESCRIPTIONS: dict[ResolutionTier, str] = {
    ResolutionTier.HIGH:   "Precision (1 m) — subsurface drip, micro-zones",
    ResolutionTier.MEDIUM: "Standard (10 m) — sprinkler block management",
    ResolutionTier.LOW:    "Overview (20 m) — pivot irrigation scheduling",
    ResolutionTier.COARSE: "Macro (50 m)  — catchment-level water balance",
}


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------
@dataclass
class SoilSample:
    """A single georeferenced soil reading."""
    x: float        # longitude or local easting (m)
    y: float        # latitude or local northing (m)
    depth_cm: float
    moisture_pct: float   # 0–100
    ec_ds_m: float = 0.0  # electrical conductivity (dS/m) — proxy for salinity


class VariabilityProfile(NamedTuple):
    """Output of a horizontal or vertical profiling pass."""
    mean:   float
    std:    float
    cv_pct: float   # coefficient of variation (%)
    min:    float
    max:    float
    range_: float


# ---------------------------------------------------------------------------
# Core math functions
# ---------------------------------------------------------------------------
def horizontal_profile(samples: list[SoilSample]) -> VariabilityProfile:
    """
    Compute spatial (horizontal) variability across a set of samples.
    Returns statistics over moisture_pct values.
    """
    if not samples:
        raise ValueError("At least one sample required.")
    vals = [s.moisture_pct for s in samples]
    return _stats(vals)


def vertical_profile(samples: list[SoilSample]) -> VariabilityProfile:
    """
    Compute depth (vertical) variability — expects samples from the
    same XY position at different depth_cm values.
    """
    if not samples:
        raise ValueError("At least one sample required.")
    depth_sorted = sorted(samples, key=lambda s: s.depth_cm)
    vals = [s.moisture_pct for s in depth_sorted]
    return _stats(vals)


def _stats(vals: list[float]) -> VariabilityProfile:
    n = len(vals)
    mean = sum(vals) / n
    variance = sum((v - mean) ** 2 for v in vals) / n
    std  = math.sqrt(variance)
    cv   = (std / mean * 100) if mean else 0.0
    return VariabilityProfile(
        mean=round(mean, 4),
        std=round(std, 4),
        cv_pct=round(cv, 2),
        min=round(min(vals), 4),
        max=round(max(vals), 4),
        range_=round(max(vals) - min(vals), 4),
    )


# ---------------------------------------------------------------------------
# Resolution tier selection
# ---------------------------------------------------------------------------
def recommend_tier(field_area_m2: float, sensor_density_per_ha: float) -> ResolutionTier:
    """
    Choose the most appropriate resolution tier based on field size
    and sensor density.

    Rules (ordered by precision preference):
      ≥ 10 sensors/ha  → HIGH (1 m)
      ≥ 2  sensors/ha  → MEDIUM (10 m)
      ≥ 0.5 sensors/ha → LOW (20 m)
      else             → COARSE (50 m)
    """
    if sensor_density_per_ha >= 10:
        return ResolutionTier.HIGH
    if sensor_density_per_ha >= 2:
        return ResolutionTier.MEDIUM
    if sensor_density_per_ha >= 0.5:
        return ResolutionTier.LOW
    return ResolutionTier.COARSE


# ---------------------------------------------------------------------------
# Irrigation volume recommendation
# ---------------------------------------------------------------------------
def irrigation_volume_mm(
    samples: list[SoilSample],
    field_capacity_pct: float = 35.0,
    root_depth_cm: float = 30.0,
) -> float:
    """
    Estimate the water deficit (mm) needed to bring the sampled zone
    to field capacity.

    Formula:  deficit_mm = (FC - current_avg) / 100 × root_depth_cm × 10
    """
    if not samples:
        raise ValueError("At least one sample required.")
    avg_moisture = sum(s.moisture_pct for s in samples) / len(samples)
    deficit = max(0.0, (field_capacity_pct - avg_moisture) / 100 * root_depth_cm * 10)
    return round(deficit, 2)
