from __future__ import annotations

from collections import deque
from dataclasses import replace
from decimal import Decimal
from typing import Iterable, Literal, Sequence

from app.concentration import (
    CONCENTRATION_SPAN_THRESHOLD,
    MIN_CLUSTER_OBSERVATIONS,
    ROUTE_OBSERVATION_WINDOW,
    ConcentrationResult,
    evaluate_concentration,
)
from app.domain import (
    ActivationSource,
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


def build_active_mrz(
    observation: Observation,
    cluster: Cluster,
    *,
    activation_source: ActivationSource = ActivationSource.PRODUCTION_QUALIFIED,
) -> ActiveMRZ | None:
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
        supporting_observation_count=cluster.observation_count,
        activated_at=observation.observed_at,
        activation_event_id=observation.event_id,
        formation_started_at=cluster.formation_started_at,
        formation_completed_at=cluster.formation_completed_at,
        formation_duration_seconds=cluster.formation_duration_seconds,
        ipda_20w_high_at_activation=observation.ipda_20w_high,
        ipda_20w_low_at_activation=observation.ipda_20w_low,
        ipda_width_at_activation=observation.ipda_width,
        normalized_span_at_activation=cluster.normalized_span,
        instrument_tick=effective_instrument_tick(cluster),
        activation_source=activation_source,
    )


SuccessorSide = Literal["UP", "DOWN"]


def successor_external_side(
    active: ActiveMRZ,
    observation: Observation,
) -> SuccessorSide | None:
    if observation.observation_price > active.upper_migration_boundary:
        return "UP"
    if observation.observation_price < active.lower_migration_boundary:
        return "DOWN"
    return None


def successor_eligible(active: ActiveMRZ, observation: Observation) -> bool:
    """Return whether an observation is external to the current authority."""
    return successor_external_side(active, observation) is not None


def successor_observation_pool(
    active: ActiveMRZ,
    route_window: Sequence[Observation],
    incoming: Observation,
) -> tuple[Observation, ...]:
    """Select the incoming observation's route and external-side pool."""
    incoming_side = successor_external_side(active, incoming)
    if incoming_side is None:
        return ()
    return tuple(
        item
        for item in route_window
        if item.route is incoming.route
        and successor_external_side(active, item) == incoming_side
    )


def build_successor_mrz(
    active: ActiveMRZ,
    incoming: Observation,
    cluster: Cluster,
) -> ActiveMRZ | None:
    """Build a structurally valid successor wholly external on one side."""
    incoming_side = successor_external_side(active, incoming)
    if incoming_side is None or any(
        item.route is not incoming.route
        or successor_external_side(active, item) != incoming_side
        for item in cluster.members
    ):
        return None
    return build_active_mrz(
        incoming,
        cluster,
        activation_source=active.activation_source,
    )


def supports_active_core_mrz(active: ActiveMRZ, observation: Observation) -> bool:
    if observation.symbol != active.symbol or observation.route is not active.route_owner:
        return False
    if not active.core_mrz_lower <= observation.observation_price <= active.core_mrz_upper:
        return False
    return (
        classify_structural_location(
            observation.route,
            observation.observation_price,
            observation.ipda_20w_high,
            observation.ipda_20w_low,
        )
        is not None
    )


def replay_symbol(
    observations: Iterable[Observation],
    *,
    minimum_required_count: int = MIN_CLUSTER_OBSERVATIONS,
    concentration_threshold: Decimal = CONCENTRATION_SPAN_THRESHOLD,
    promoted_activation: ActiveMRZ | None = None,
) -> ReplayResult:
    ordered = sorted(observations, key=lambda item: item.order_key)
    if not ordered:
        return ReplayResult(symbol="", active_mrz=None, transitions=(), latest_observation=None)
    symbol = ordered[0].symbol
    if any(item.symbol != symbol for item in ordered):
        raise ValueError("replay_symbol accepts exactly one normalized symbol")
    if promoted_activation is not None and promoted_activation.symbol != symbol:
        raise ValueError("promoted activation must belong to the replayed symbol")

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
            if (
                promoted_activation is not None
                and incoming.event_id == promoted_activation.activation_event_id
            ):
                active = promoted_activation
                transitions.append(
                    MRZTransition(
                        sequence=len(transitions) + 1,
                        event_type=MRZEventType.ACTIVATED,
                        symbol=symbol,
                        route_owner=active.route_owner,
                        previous_route_owner=None,
                        occurred_at=active.activated_at,
                        trigger_event_id=incoming.event_id,
                        old_mrz=None,
                        new_mrz=active,
                        details={
                            "reason": "current_production_near_miss_operator_promoted",
                            "activation_source": ActivationSource.OPERATOR_PROMOTED.value,
                        },
                    )
                )
                continue
            evaluation = evaluate_concentration(
                tuple(route_window),
                incoming.route,
                minimum_required_count=minimum_required_count,
                concentration_threshold=concentration_threshold,
            )
            candidate = (
                build_active_mrz(incoming, evaluation.cluster)
                if evaluation.result is ConcentrationResult.QUALIFIES and evaluation.cluster
                else None
            )
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

        if supports_active_core_mrz(active, incoming):
            active = replace(
                active,
                supporting_observation_count=active.supporting_observation_count + 1,
            )
            continue

        if not successor_eligible(active, incoming):
            continue
        eligible_pool = successor_observation_pool(
            active,
            tuple(route_window),
            incoming,
        )
        evaluation = evaluate_concentration(
            eligible_pool,
            incoming.route,
            minimum_required_count=minimum_required_count,
            concentration_threshold=concentration_threshold,
        )
        successor = (
            build_successor_mrz(active, incoming, evaluation.cluster)
            if evaluation.result is ConcentrationResult.QUALIFIES and evaluation.cluster
            else None
        )
        if successor is None:
            continue
        previous = active
        active = successor
        migration_side = successor_external_side(previous, incoming)
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
                    "reason": "external_successor_concentration_confirmed",
                    "external_side": migration_side,
                    "candidate_route": active.route_owner.value,
                    "old_lower_migration_boundary": str(previous.lower_migration_boundary),
                    "old_upper_migration_boundary": str(previous.upper_migration_boundary),
                },
            )
        )
        if previous.route_owner is not active.route_owner:
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
                    details={
                        "reason": "successor_route_changed",
                        "external_side": migration_side,
                    },
                )
            )

    return ReplayResult(
        symbol=symbol,
        active_mrz=active,
        transitions=tuple(transitions),
        latest_observation=ordered[-1],
    )
