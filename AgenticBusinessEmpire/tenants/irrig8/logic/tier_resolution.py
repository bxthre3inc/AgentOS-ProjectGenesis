"""
tier_resolution.py — Irrig8 Resolution Funnel

Implements the UI 'pop' resolution logic for the 1m / 10m / 20m / 50m tiers.

The funnel determines which resolution layer to DISPLAY based on:
  - current map zoom level
  - available sensor density
  - user's subscription tier (Lite / Pro / Enterprise)

This module is UI-ready: it exposes a simple `resolve(context) -> TierResult`
function that the front-end calls to get the active tier and a set of
display metadata flags.

Tier hierarchy (finest → coarsest):
  1 m  →  10 m  →  20 m  →  50 m

The funnel 'pops' upward (coarser) when sensor density or zoom level is
insufficient.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Literal

from math_engine import ResolutionTier, TIER_DESCRIPTIONS   # sibling import


# ---------------------------------------------------------------------------
# Subscription tiers (UI access control)
# ---------------------------------------------------------------------------
class SubscriptionTier(str, Enum):
    LITE       = "lite"       # 50 m only
    PRO        = "pro"        # 50 m + 20 m + 10 m
    ENTERPRISE = "enterprise" # all tiers (1 m enabled)


TIER_ACCESS: dict[SubscriptionTier, set[ResolutionTier]] = {
    SubscriptionTier.LITE:       {ResolutionTier.COARSE},
    SubscriptionTier.PRO:        {ResolutionTier.COARSE, ResolutionTier.LOW, ResolutionTier.MEDIUM},
    SubscriptionTier.ENTERPRISE: set(ResolutionTier),
}


# ---------------------------------------------------------------------------
# Resolution context (input)
# ---------------------------------------------------------------------------
@dataclass
class ResolutionContext:
    zoom_level:           float   # 1–20 (like Google Maps)
    sensor_density_per_ha: float
    field_area_m2:        float
    subscription:         SubscriptionTier = SubscriptionTier.PRO


# ---------------------------------------------------------------------------
# Tier result (output — directly consumed by UI)
# ---------------------------------------------------------------------------
@dataclass
class TierResult:
    active_tier:     ResolutionTier
    resolution_m:    int
    label:           str
    is_max_allowed:  bool       # True = user is at finest available tier
    upgrade_prompt:  str | None # non-None if a finer tier exists behind paywall
    pop_reason:      str | None # why we fell back from a finer tier


# ---------------------------------------------------------------------------
# Funnel logic
# ---------------------------------------------------------------------------

# Minimum zoom level required to render each tier meaningfully
_MIN_ZOOM: dict[ResolutionTier, float] = {
    ResolutionTier.HIGH:   17.0,
    ResolutionTier.MEDIUM: 14.0,
    ResolutionTier.LOW:    12.0,
    ResolutionTier.COARSE: 9.0,
}

# Minimum sensor density (sensors/ha) for each tier
_MIN_DENSITY: dict[ResolutionTier, float] = {
    ResolutionTier.HIGH:   10.0,
    ResolutionTier.MEDIUM: 2.0,
    ResolutionTier.LOW:    0.5,
    ResolutionTier.COARSE: 0.0,
}


def resolve(ctx: ResolutionContext) -> TierResult:
    """
    Walk the funnel from finest → coarsest and return the first tier that:
      a) the user's subscription unlocks
      b) the current zoom supports
      c) the sensor density supports

    Returns a TierResult with display metadata.
    """
    ordered = [
        ResolutionTier.HIGH,
        ResolutionTier.MEDIUM,
        ResolutionTier.LOW,
        ResolutionTier.COARSE,
    ]
    allowed_tiers = TIER_ACCESS[ctx.subscription]
    pop_reason: str | None = None
    upgrade_prompt: str | None = None

    for tier in ordered:
        # Subscription gate
        if tier not in allowed_tiers:
            if tier == ResolutionTier.HIGH and ctx.subscription != SubscriptionTier.ENTERPRISE:
                upgrade_prompt = "Upgrade to Enterprise to unlock 1 m precision mapping."
            continue

        # Zoom gate
        if ctx.zoom_level < _MIN_ZOOM[tier]:
            pop_reason = f"Zoom in to activate {tier.value} m layer (need zoom ≥ {_MIN_ZOOM[tier]:.0f})."
            continue

        # Density gate
        if ctx.sensor_density_per_ha < _MIN_DENSITY[tier]:
            pop_reason = (
                f"Sensor density {ctx.sensor_density_per_ha:.1f}/ha insufficient for "
                f"{tier.value} m layer (need ≥ {_MIN_DENSITY[tier]}/ha)."
            )
            continue

        # Winner
        finer = [t for t in ordered[:ordered.index(tier)] if t not in allowed_tiers]
        is_max = len(finer) == 0 or all(t not in allowed_tiers for t in finer)

        return TierResult(
            active_tier=tier,
            resolution_m=tier.value,
            label=TIER_DESCRIPTIONS[tier],
            is_max_allowed=is_max,
            upgrade_prompt=upgrade_prompt,
            pop_reason=pop_reason,
        )

    # Fallback — always deliver 50 m
    return TierResult(
        active_tier=ResolutionTier.COARSE,
        resolution_m=50,
        label=TIER_DESCRIPTIONS[ResolutionTier.COARSE],
        is_max_allowed=False,
        upgrade_prompt=upgrade_prompt,
        pop_reason=pop_reason or "Defaulting to 50 m coarse layer.",
    )
