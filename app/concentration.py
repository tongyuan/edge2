from __future__ import annotations

from decimal import Decimal
from typing import Sequence

from app.domain import Cluster, Observation


MIN_CLUSTER_OBSERVATIONS = 4
ROUTE_OBSERVATION_WINDOW = 20
CONCENTRATION_SPAN_THRESHOLD = Decimal("0.01")


def latest_route_window(observations: Sequence[Observation]) -> list[Observation]:
    return sorted(observations, key=lambda item: item.order_key)[-ROUTE_OBSERVATION_WINDOW:]


def select_cluster(
    observations: Sequence[Observation],
    incoming_event_id: str,
    ipda_width: Decimal,
) -> Cluster | None:
    if len(observations) < MIN_CLUSTER_OBSERVATIONS:
        return None
    if not ipda_width.is_finite() or ipda_width <= 0:
        raise ValueError("ipda_width must be finite and positive")

    price_sorted = sorted(
        observations,
        key=lambda item: (item.observation_price, item.order_key),
    )
    maximum_span = CONCENTRATION_SPAN_THRESHOLD * ipda_width
    seeds: list[tuple[Decimal, Decimal, Decimal, tuple[tuple[object, ...], ...], int]] = []
    for start in range(0, len(price_sorted) - MIN_CLUSTER_OBSERVATIONS + 1):
        window = price_sorted[start : start + MIN_CLUSTER_OBSERVATIONS]
        if not any(item.event_id == incoming_event_id for item in window):
            continue
        span = window[-1].observation_price - window[0].observation_price
        if span <= maximum_span:
            seeds.append(
                (
                    span,
                    window[0].observation_price,
                    window[-1].observation_price,
                    tuple(item.order_key for item in window),
                    start,
                )
            )
    if not seeds:
        return None

    _span, _lower, _upper, _orders, seed_start = min(seeds)
    left = seed_start
    right = seed_start + MIN_CLUSTER_OBSERVATIONS - 1

    while True:
        choices: list[tuple[Decimal, int, tuple[object, ...], str]] = []
        if left > 0:
            candidate = price_sorted[left - 1]
            span = price_sorted[right].observation_price - candidate.observation_price
            if span <= maximum_span:
                choices.append((span, 0, candidate.order_key, "left"))
        if right + 1 < len(price_sorted):
            candidate = price_sorted[right + 1]
            span = candidate.observation_price - price_sorted[left].observation_price
            if span <= maximum_span:
                choices.append((span, 1, candidate.order_key, "right"))
        if not choices:
            break
        _choice_span, _side_order, _order_key, side = min(choices)
        if side == "left":
            left -= 1
        else:
            right += 1

    members = tuple(price_sorted[left : right + 1])
    lower = members[0].observation_price
    upper = members[-1].observation_price
    span = upper - lower
    return Cluster(
        members=members,
        lower=lower,
        upper=upper,
        midpoint=(lower + upper) / Decimal("2"),
        normalized_span=span / ipda_width,
    )
