from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Sequence

from app.domain import Observation
from app.mrz_evidence import PostActivationEvidence


MIN_MEANINGFUL_OUTSIDE_ENVELOPE_OBSERVATIONS = 2
MIN_DIRECTIONAL_ENVELOPE_LEAD = 2
DIRECTIONAL_ENVELOPE_SHARE_NUMERATOR = 3
DIRECTIONAL_ENVELOPE_SHARE_DENOMINATOR = 5
CURRENT_PRESSURE_RECENT_WINDOW = 4
CURRENT_PRESSURE_CONFIRMATION_COUNT = 3


@dataclass(frozen=True, slots=True)
class PostActivationState:
    status: str
    label: str
    reason: str
    direction: str
    direction_label: str


@dataclass(frozen=True, slots=True)
class DirectionalPressureObservation:
    observation: Observation
    direction: str


@dataclass(frozen=True, slots=True)
class CurrentPressureRegime:
    state: PostActivationState
    recent_evidence: tuple[DirectionalPressureObservation, ...]
    current_pressure_since: datetime | None
    latest_pressure_observed_at: datetime | None

    @property
    def recent_higher_count(self) -> int:
        return sum(item.direction == "UP" for item in self.recent_evidence)

    @property
    def recent_lower_count(self) -> int:
        return sum(item.direction == "DOWN" for item in self.recent_evidence)


def classify_cumulative_pressure(evidence: PostActivationEvidence) -> PostActivationState:
    """Interpret factual lifecycle evidence using the existing Pressure policy."""
    return classify_cumulative_pressure_counts(
        evidence.total_observation_count,
        evidence.above_envelope_count,
        evidence.below_envelope_count,
    )


def classify_cumulative_pressure_counts(
    total_observation_count: int,
    above_envelope_count: int,
    below_envelope_count: int,
) -> PostActivationState:
    """Compatibility entry point for the existing count-based policy."""
    if total_observation_count == 0:
        return PostActivationState(
            status="NO_EVIDENCE",
            label="No evidence",
            reason="No post-activation observations are available to assess behavior.",
            direction="NEUTRAL",
            direction_label="Neutral",
        )

    outside_count = above_envelope_count + below_envelope_count
    if outside_count < MIN_MEANINGFUL_OUTSIDE_ENVELOPE_OBSERVATIONS:
        reason = (
            "No post-activation observation is beyond the active MRZ migration envelope."
            if outside_count == 0
            else (
                "Only one post-activation observation is beyond the active MRZ "
                "migration envelope; this is not enough to establish directional pressure."
            )
        )
        return PostActivationState(
            status="STABLE",
            label="Contained / Quiet",
            reason=reason,
            direction="NEUTRAL",
            direction_label="Neutral",
        )

    def materially_dominates(dominant_count: int, other_count: int) -> bool:
        return (
            dominant_count - other_count >= MIN_DIRECTIONAL_ENVELOPE_LEAD
            and dominant_count * DIRECTIONAL_ENVELOPE_SHARE_DENOMINATOR
            >= outside_count * DIRECTIONAL_ENVELOPE_SHARE_NUMERATOR
        )

    if materially_dominates(above_envelope_count, below_envelope_count):
        return PostActivationState(
            status="UNDER_PRESSURE",
            label="Upward Pressure",
            reason="Above-envelope activity materially dominates below-envelope activity.",
            direction="UP",
            direction_label="Upward",
        )
    if materially_dominates(below_envelope_count, above_envelope_count):
        return PostActivationState(
            status="UNDER_PRESSURE",
            label="Downward Pressure",
            reason="Below-envelope activity materially dominates above-envelope activity.",
            direction="DOWN",
            direction_label="Downward",
        )
    return PostActivationState(
        status="STABLE",
        label="Two-sided / Consolidating",
        reason=(
            "Post-activation observations are distributed on both sides of the active "
            "MRZ with no meaningful directional dominance."
        ),
        direction="NEUTRAL",
        direction_label="Neutral",
    )


def classify_current_pressure_directions(
    directions: Sequence[str],
) -> PostActivationState:
    """Classify the existing latest-four Pressure projection."""
    recent = tuple(directions[-CURRENT_PRESSURE_RECENT_WINDOW:])
    evidence_count = len(recent)
    higher_count = recent.count("UP")
    lower_count = recent.count("DOWN")
    if evidence_count == 0:
        return PostActivationState(
            status="NO_EVIDENCE",
            label="No current pressure evidence",
            reason=(
                "No post-activation observation is beyond the active MRZ "
                "migration envelope."
            ),
            direction="NEUTRAL",
            direction_label="Neutral",
        )
    if evidence_count < CURRENT_PRESSURE_CONFIRMATION_COUNT:
        return PostActivationState(
            status="INSUFFICIENT_EVIDENCE",
            label="Insufficient recent pressure evidence",
            reason=(
                f"{evidence_count} recent qualifying pressure observation"
                f"{' is' if evidence_count == 1 else 's are'} available; "
                f"{CURRENT_PRESSURE_CONFIRMATION_COUNT} are required to establish "
                "the current pressure regime."
            ),
            direction="NEUTRAL",
            direction_label="Neutral",
        )
    if higher_count >= CURRENT_PRESSURE_CONFIRMATION_COUNT:
        return PostActivationState(
            status="UNDER_PRESSURE",
            label="Upward Pressure",
            reason=(
                f"{higher_count} of the latest {evidence_count} qualifying pressure "
                "observations are above the active MRZ migration envelope."
            ),
            direction="UP",
            direction_label="Upward",
        )
    if lower_count >= CURRENT_PRESSURE_CONFIRMATION_COUNT:
        return PostActivationState(
            status="UNDER_PRESSURE",
            label="Downward Pressure",
            reason=(
                f"{lower_count} of the latest {evidence_count} qualifying pressure "
                "observations are below the active MRZ migration envelope."
            ),
            direction="DOWN",
            direction_label="Downward",
        )
    return PostActivationState(
        status="STABLE",
        label="Neutral / Mixed",
        reason=(
            f"The latest {evidence_count} qualifying pressure observations do not "
            f"contain {CURRENT_PRESSURE_CONFIRMATION_COUNT} observations on either "
            "side of the active MRZ migration envelope."
        ),
        direction="NEUTRAL",
        direction_label="Neutral",
    )


def derive_current_pressure_regime(
    evidence: PostActivationEvidence,
) -> CurrentPressureRegime:
    """Interpret factual external observations through the current Pressure policy."""
    directional = tuple(
        DirectionalPressureObservation(item.observation, item.side)
        for item in evidence.external_observations
    )
    state = classify_current_pressure_directions(
        tuple(item.direction for item in directional)
    )
    previous_direction = "NEUTRAL"
    current_pressure_since = None
    for index, item in enumerate(directional, 1):
        next_state = classify_current_pressure_directions(
            tuple(row.direction for row in directional[:index])
        )
        if next_state.direction != previous_direction:
            current_pressure_since = item.observation.observed_at
            previous_direction = next_state.direction
    return CurrentPressureRegime(
        state=state,
        recent_evidence=directional[-CURRENT_PRESSURE_RECENT_WINDOW:],
        current_pressure_since=current_pressure_since,
        latest_pressure_observed_at=(
            directional[-1].observation.observed_at if directional else None
        ),
    )
