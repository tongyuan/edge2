from __future__ import annotations

from decimal import Decimal
from typing import Literal


Direction = Literal["LONG", "SHORT"]
MinimumGrade = Literal["Off", "A", "A+"]
ConfirmationMethod = Literal["CE_RECLAIM", "PROXIMAL_RECLAIM"]


def grade_meets(current: str | None, required: MinimumGrade) -> bool:
    if required == "Off":
        return True
    rank = {None: 0, "": 0, "A": 1, "A+": 2}
    return rank.get(current, 0) >= rank[required]


def range_third_bounds(
    direction: Direction,
    range_low: Decimal,
    range_high: Decimal,
) -> tuple[Decimal, Decimal]:
    width = range_high - range_low
    if direction == "LONG":
        return range_low, range_low + width / 3
    return range_high - width / 3, range_high


def intersect_entry_zone(
    *,
    direction: Direction,
    range_low: Decimal,
    range_high: Decimal,
    source_bottom: Decimal,
    source_top: Decimal,
    ote_required: bool,
    ote_bottom: Decimal | None = None,
    ote_top: Decimal | None = None,
) -> tuple[Decimal, Decimal] | None:
    third_bottom, third_top = range_third_bounds(direction, range_low, range_high)
    bottom = max(source_bottom, third_bottom)
    top = min(source_top, third_top)
    if ote_required:
        if ote_bottom is None or ote_top is None:
            return None
        bottom = max(bottom, ote_bottom)
        top = min(top, ote_top)
    return (bottom, top) if top > bottom else None


def confirmation_satisfied(
    *,
    direction: Direction,
    method: ConfirmationMethod,
    close: Decimal,
    zone_bottom: Decimal,
    zone_top: Decimal,
) -> bool:
    threshold = (
        (zone_bottom + zone_top) / 2
        if method == "CE_RECLAIM"
        else (zone_top if direction == "LONG" else zone_bottom)
    )
    return close > threshold if direction == "LONG" else close < threshold
