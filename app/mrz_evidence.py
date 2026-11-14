from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Sequence

from app.domain import ActiveMRZ, Observation
from app.state_engine import successor_external_side


@dataclass(frozen=True, slots=True)
class ExternalObservation:
    """One factual observation outside the active migration envelope."""

    observation: Observation
    side: str


@dataclass(frozen=True, slots=True)
class PostActivationEvidence:
    """Pressure-neutral measurements for one active MRZ lifecycle."""

    observations: tuple[Observation, ...]
    external_observations: tuple[ExternalObservation, ...]
    inside_mrz_count: int
    above_mrz_count: int
    below_mrz_count: int
    upper_boundary_test_count: int
    lower_boundary_test_count: int
    above_envelope_count: int
    below_envelope_count: int
    midpoint_displacements: tuple[Decimal, ...]

    @property
    def total_observation_count(self) -> int:
        return len(self.observations)


def select_post_activation_observations(
    active: ActiveMRZ,
    observations: Sequence[Observation],
) -> tuple[Observation, ...]:
    """Select observations after the current activation in canonical order."""
    ordered = tuple(sorted(observations, key=lambda item: item.order_key))
    activation = next(
        (item for item in ordered if item.event_id == active.activation_event_id),
        None,
    )
    if activation is not None:
        return tuple(item for item in ordered if item.order_key > activation.order_key)
    return tuple(item for item in ordered if item.observed_at > active.activated_at)


def build_post_activation_evidence(
    active: ActiveMRZ,
    observations: Sequence[Observation],
) -> PostActivationEvidence:
    """Measure post-activation geometry without assigning Pressure meaning."""
    post_activation = select_post_activation_observations(active, observations)
    external = tuple(
        ExternalObservation(observation, side)
        for observation in post_activation
        if (side := successor_external_side(active, observation)) is not None
    )
    return PostActivationEvidence(
        observations=post_activation,
        external_observations=external,
        inside_mrz_count=sum(
            active.core_mrz_lower
            <= observation.observation_price
            <= active.core_mrz_upper
            for observation in post_activation
        ),
        above_mrz_count=sum(
            observation.observation_price > active.core_mrz_upper
            for observation in post_activation
        ),
        below_mrz_count=sum(
            observation.observation_price < active.core_mrz_lower
            for observation in post_activation
        ),
        upper_boundary_test_count=sum(
            observation.observation_price >= active.core_mrz_upper
            for observation in post_activation
        ),
        lower_boundary_test_count=sum(
            observation.observation_price <= active.core_mrz_lower
            for observation in post_activation
        ),
        above_envelope_count=sum(item.side == "UP" for item in external),
        below_envelope_count=sum(item.side == "DOWN" for item in external),
        midpoint_displacements=tuple(
            (observation.observation_price - active.core_mrz_midpoint)
            / active.ipda_width_at_activation
            * Decimal("100")
            for observation in post_activation
        ),
    )
