from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Iterable

from app.concentration import CONCENTRATION_SPAN_THRESHOLD, MIN_CLUSTER_OBSERVATIONS
from app.domain import ActiveMRZ, MRZEventType, Observation, Route
from app.state_engine import replay_symbol


@dataclass(frozen=True, slots=True)
class Episode:
    symbol: str
    generation: int
    active_mrz: ActiveMRZ
    activation_observation: Observation
    source_observations: tuple[Observation, ...]
    activation_index: int
    termination_index: int | None
    termination_event_type: MRZEventType | None
    termination_event_id: str | None
    migration_direction: str | None
    outcome: str

    @property
    def post_activation_observations(self) -> tuple[Observation, ...]:
        stop = (
            self.termination_index + 1
            if self.termination_index is not None
            else len(self.source_observations)
        )
        return self.source_observations[self.activation_index + 1 : stop]

    @property
    def ended_at(self) -> datetime | None:
        if self.termination_index is None:
            return None
        return self.source_observations[self.termination_index].observed_at

    @property
    def is_ongoing(self) -> bool:
        return self.termination_index is None


@dataclass(frozen=True, slots=True)
class Reconstruction:
    episodes: tuple[Episode, ...]
    exclusions: tuple[dict[str, str], ...]


def reconstruct_episodes(
    observations: Iterable[Observation],
    *,
    minimum_required_count: int = MIN_CLUSTER_OBSERVATIONS,
    concentration_threshold: Decimal = CONCENTRATION_SPAN_THRESHOLD,
) -> Reconstruction:
    """Replay authoritative MRZ generations for retained robustness research."""
    by_symbol: dict[str, list[Observation]] = defaultdict(list)
    for item in observations:
        by_symbol[item.symbol].append(item)

    episodes: list[Episode] = []
    exclusions: list[dict[str, str]] = []
    for symbol in sorted(by_symbol):
        ordered = tuple(sorted(by_symbol[symbol], key=lambda item: item.order_key))
        by_event_id = {item.event_id: index for index, item in enumerate(ordered)}
        replay = replay_symbol(
            ordered,
            minimum_required_count=minimum_required_count,
            concentration_threshold=concentration_threshold,
        )
        transitions = tuple(
            transition
            for transition in replay.transitions
            if transition.event_type in {MRZEventType.ACTIVATED, MRZEventType.MIGRATED}
        )
        for transition_index, transition in enumerate(transitions):
            activation_index = by_event_id.get(transition.trigger_event_id)
            if activation_index is None:
                exclusions.append(
                    {
                        "symbol": symbol,
                        "activation_event_id": transition.trigger_event_id,
                        "reason": "activation trigger observation is missing",
                    }
                )
                continue
            next_transition = (
                transitions[transition_index + 1]
                if transition_index + 1 < len(transitions)
                else None
            )
            termination_index = (
                by_event_id.get(next_transition.trigger_event_id)
                if next_transition is not None
                else None
            )
            if next_transition is not None and termination_index is None:
                exclusions.append(
                    {
                        "symbol": symbol,
                        "activation_event_id": transition.trigger_event_id,
                        "reason": "termination trigger observation is missing",
                    }
                )
                continue

            migration_direction: str | None = None
            outcome = "ONGOING"
            if next_transition is not None:
                old_midpoint = transition.new_mrz.core_mrz_midpoint
                new_midpoint = next_transition.new_mrz.core_mrz_midpoint
                if new_midpoint > old_midpoint:
                    migration_direction = "UPWARD"
                    outcome = "MIGRATED_UPWARD"
                elif new_midpoint < old_midpoint:
                    migration_direction = "DOWNWARD"
                    outcome = "MIGRATED_DOWNWARD"
                else:
                    migration_direction = "LATERAL"
                    outcome = "MIGRATED_LATERAL"

            episodes.append(
                Episode(
                    symbol=symbol,
                    generation=transition_index + 1,
                    active_mrz=transition.new_mrz,
                    activation_observation=ordered[activation_index],
                    source_observations=ordered,
                    activation_index=activation_index,
                    termination_index=termination_index,
                    termination_event_type=(
                        next_transition.event_type if next_transition else None
                    ),
                    termination_event_id=(
                        next_transition.trigger_event_id if next_transition else None
                    ),
                    migration_direction=migration_direction,
                    outcome=outcome,
                )
            )

    return Reconstruction(tuple(episodes), tuple(exclusions))


def signed_displacement(active: ActiveMRZ, observation: Observation) -> Decimal:
    return (
        observation.observation_price - active.core_mrz_midpoint
    ) / active.ipda_width_at_activation


def route_interpretation(route: Route, displacement: Decimal) -> str:
    if displacement == 0:
        return "NEUTRAL"
    supportive = displacement > 0 if route is Route.BTD else displacement < 0
    return "ROUTE_SUPPORTIVE" if supportive else "ROUTE_ADVERSE"


def first_timing(
    episode: Episode,
    predicate: Any,
) -> tuple[int, Decimal] | None:
    for index, observation in enumerate(episode.post_activation_observations, 1):
        if predicate(index, observation):
            elapsed = Decimal(
                str(
                    (
                        observation.observed_at - episode.active_mrz.activated_at
                    ).total_seconds()
                )
            )
            return index, elapsed / Decimal("3600")
    return None
