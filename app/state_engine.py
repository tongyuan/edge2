from __future__ import annotations

from collections import deque
from decimal import Decimal
from typing import Iterable, Sequence

from app.concentration import ROUTE_OBSERVATION_WINDOW, select_cluster
from app.domain import (
    ActiveMRZ,
    Cluster,
    MRZEventType,
    MRZTransition,
    Observation,
    ReplayResult,
    Route,
)
from app.structure import classify_structural_location


def effective_instrument_tick(cluster: Cluster) -> Decimal:
    ticks = [member.observation_price_tick for member in cluster.members if member.observation_price_tick > 0]
    if not ticks:
        raise ValueError("cluster observations must carry a positive tick")
    return min(ticks)


def build_active_mrz(observation: Observation, cluster: Cluster) -> ActiveMRZ | None:
    location = classify_structural_location(
        observation.route,
        cluster.midpoint,
        observation.ipda_20w_high,
        observation.ipda_20w_low,
    )
    if location is None:
        return None
    return ActiveMRZ(
        symbol=observation.symbol,
        route_owner=observation.route,
        core_mrz_lower=cluster.lower,
        core_mrz_upper=cluster.upper,
        core_mrz_midpoint=cluster.midpoint,
        structural_location=location,
        confirming_observation_count=cluster.observation_count,
        activated_at=observation.observed_at,
        activation_event_id=observation.event_id,
        ipda_20w_high_at_activation=observation.ipda_20w_high,
        ipda_20w_low_at_activation=observation.ipda_20w_low,
        ipda_width_at_activation=observation.ipda_width,
        normalized_span_at_activation=cluster.normalized_span,
        instrument_tick=effective_instrument_tick(cluster),
    )


def successor_eligible(active: ActiveMRZ, observation: Observation) -> bool:
    if observation.route is not active.route_owner:
        return False
    if active.route_owner is Route.BTD:
        return observation.observation_price > active.upper_migration_boundary
    return observation.observation_price < active.lower_migration_boundary


def evaluate_cross_route_replacement(
    active: ActiveMRZ,
    incoming: Observation,
    route_window: Sequence[Observation],
) -> ActiveMRZ | None:
    """Frozen 4.3 doctrine defines no cross-route replacement trigger.

    This explicit boundary keeps route replacement architecturally isolated without
    inventing a handover, recommendation, or opposite-route authority rule.
    """
    del active, incoming, route_window
    return None


def replay_symbol(observations: Iterable[Observation]) -> ReplayResult:
    ordered = sorted(observations, key=lambda item: item.order_key)
    if not ordered:
        return ReplayResult(symbol="", active_mrz=None, transitions=(), latest_observation=None)
    symbol = ordered[0].symbol
    if any(item.symbol != symbol for item in ordered):
        raise ValueError("replay_symbol accepts exactly one normalized symbol")

    windows: dict[Route, deque[Observation]] = {
        Route.BTD: deque(maxlen=ROUTE_OBSERVATION_WINDOW),
        Route.STR: deque(maxlen=ROUTE_OBSERVATION_WINDOW),
    }
    active: ActiveMRZ | None = None
    transitions: list[MRZTransition] = []

    for incoming in ordered:
        route_window = windows[incoming.route]
        route_window.append(incoming)

        if active is None:
            cluster = select_cluster(tuple(route_window), incoming.event_id, incoming.ipda_width)
            candidate = build_active_mrz(incoming, cluster) if cluster else None
            if candidate is None:
                continue
            active = candidate
            transitions.append(
                MRZTransition(
                    sequence=len(transitions) + 1,
                    event_type=MRZEventType.ACTIVATED,
                    symbol=symbol,
                    route_owner=active.route_owner,
                    previous_route_owner=None,
                    occurred_at=incoming.observed_at,
                    trigger_event_id=incoming.event_id,
                    old_mrz=None,
                    new_mrz=active,
                    details={"reason": "four_observation_concentration_confirmed"},
                )
            )
            continue

        if incoming.route is not active.route_owner:
            replacement = evaluate_cross_route_replacement(active, incoming, tuple(route_window))
            if replacement is not None:
                previous = active
                active = replacement
                transitions.append(
                    MRZTransition(
                        sequence=len(transitions) + 1,
                        event_type=MRZEventType.ROUTE_CHANGED,
                        symbol=symbol,
                        route_owner=active.route_owner,
                        previous_route_owner=previous.route_owner,
                        occurred_at=incoming.observed_at,
                        trigger_event_id=incoming.event_id,
                        old_mrz=previous,
                        new_mrz=active,
                        details={"reason": "cross_route_replacement"},
                    )
                )
            continue

        if not successor_eligible(active, incoming):
            continue
        eligible_pool = tuple(item for item in route_window if successor_eligible(active, item))
        cluster = select_cluster(eligible_pool, incoming.event_id, incoming.ipda_width)
        successor = build_active_mrz(incoming, cluster) if cluster else None
        if successor is None:
            continue
        previous = active
        active = successor
        transitions.append(
            MRZTransition(
                sequence=len(transitions) + 1,
                event_type=MRZEventType.MIGRATED,
                symbol=symbol,
                route_owner=active.route_owner,
                previous_route_owner=previous.route_owner,
                occurred_at=incoming.observed_at,
                trigger_event_id=incoming.event_id,
                old_mrz=previous,
                new_mrz=active,
                details={
                    "reason": "same_route_successor_concentration_confirmed",
                    "old_lower_migration_boundary": str(previous.lower_migration_boundary),
                    "old_upper_migration_boundary": str(previous.upper_migration_boundary),
                },
            )
        )

    return ReplayResult(
        symbol=symbol,
        active_mrz=active,
        transitions=tuple(transitions),
        latest_observation=ordered[-1],
    )
