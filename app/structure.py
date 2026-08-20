from __future__ import annotations

from decimal import Decimal

from app.domain import PriceLocation, Route, StructuralLocation


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
    location = classify_ipda_location(midpoint, ipda_high, ipda_low)
    route_locations = {
        Route.BTD: {
            PriceLocation.DEEP_DISCOUNT: StructuralLocation.DEEP_DISCOUNT,
            PriceLocation.SHALLOW_DISCOUNT: StructuralLocation.SHALLOW_DISCOUNT,
        },
        Route.STR: {
            PriceLocation.SHALLOW_PREMIUM: StructuralLocation.SHALLOW_PREMIUM,
            PriceLocation.DEEP_PREMIUM: StructuralLocation.DEEP_PREMIUM,
        },
    }
    return route_locations[route].get(location)


def classify_ipda_location(
    value: Decimal,
    ipda_high: Decimal,
    ipda_low: Decimal,
) -> PriceLocation | None:
    if not value.is_finite():
        raise ValueError("IPDA classification value must be finite")
    geometry = structural_geometry(ipda_high, ipda_low)
    if value < ipda_low:
        return PriceLocation.BELOW_IPDA_RANGE
    if value < geometry["discount_midpoint"]:
        return PriceLocation.DEEP_DISCOUNT
    if value < geometry["eqm"]:
        return PriceLocation.SHALLOW_DISCOUNT
    if value == geometry["eqm"]:
        return None
    if value <= geometry["premium_midpoint"]:
        return PriceLocation.SHALLOW_PREMIUM
    if value <= ipda_high:
        return PriceLocation.DEEP_PREMIUM
    return PriceLocation.ABOVE_IPDA_RANGE
