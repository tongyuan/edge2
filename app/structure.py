from __future__ import annotations

from decimal import Decimal

from app.domain import Route, StructuralLocation


def structural_geometry(ipda_high: Decimal, ipda_low: Decimal) -> dict[str, Decimal]:
    if not ipda_high.is_finite() or not ipda_low.is_finite() or ipda_high <= ipda_low:
        raise ValueError("IPDA high must be finite and greater than IPDA low")
    eqm = (ipda_high + ipda_low) / Decimal("2")
    return {
        "ipda_width": ipda_high - ipda_low,
        "eqm": eqm,
        "discount_midpoint": (ipda_low + eqm) / Decimal("2"),
        "premium_midpoint": (eqm + ipda_high) / Decimal("2"),
    }


def classify_structural_location(
    route: Route,
    midpoint: Decimal,
    ipda_high: Decimal,
    ipda_low: Decimal,
) -> StructuralLocation | None:
    geometry = structural_geometry(ipda_high, ipda_low)
    eqm = geometry["eqm"]
    if route is Route.BTD:
        if ipda_low <= midpoint < geometry["discount_midpoint"]:
            return StructuralLocation.DEEP_DISCOUNT
        if geometry["discount_midpoint"] <= midpoint < eqm:
            return StructuralLocation.SHALLOW_DISCOUNT
        return None
    if eqm < midpoint <= geometry["premium_midpoint"]:
        return StructuralLocation.SHALLOW_PREMIUM
    if geometry["premium_midpoint"] < midpoint <= ipda_high:
        return StructuralLocation.DEEP_PREMIUM
    return None
