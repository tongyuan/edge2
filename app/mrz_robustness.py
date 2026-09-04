from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Callable, Mapping, Sequence

from app.concentration import (
    CONCENTRATION_SPAN_THRESHOLD,
    MIN_CLUSTER_OBSERVATIONS,
    ConcentrationEvaluation,
    ConcentrationResult,
    evaluate_concentration,
    latest_route_window,
)
from app.domain import ActiveMRZ, Observation, Route
from app.state_engine import build_successor_mrz
from app.structure import classify_structural_location


RobustnessInputProvider = Callable[
    [],
    tuple[
        tuple[ActiveMRZ, ...],
        tuple[Observation, ...],
        Mapping[str, Mapping[str, object]],
    ],
]


MIN_MEANINGFUL_OUTSIDE_ENVELOPE_OBSERVATIONS = 2
MIN_DIRECTIONAL_ENVELOPE_LEAD = 2
DIRECTIONAL_ENVELOPE_SHARE_NUMERATOR = 3
DIRECTIONAL_ENVELOPE_SHARE_DENOMINATOR = 5


def iso(value: datetime | None) -> str | None:
    return None if value is None else value.isoformat().replace("+00:00", "Z")


def decimal_text(value: Decimal | None) -> str | None:
    return None if value is None else format(value, "f")


def median_decimal(values: Sequence[Decimal]) -> Decimal | None:
    if not values:
        return None
    ordered = sorted(values)
    midpoint = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[midpoint]
    return (ordered[midpoint - 1] + ordered[midpoint]) / Decimal("2")


def duration_seconds(start: datetime, end: datetime) -> Decimal:
    duration = end - start
    if duration.total_seconds() < 0:
        duration = end - end
    whole_seconds = (duration.days * 86400) + duration.seconds
    return Decimal(whole_seconds) + (
        Decimal(duration.microseconds) / Decimal("1000000")
    )


def current_formation_provenance(
    active: ActiveMRZ,
) -> tuple[datetime, datetime, Decimal] | None:
    """Return validated formation provenance for the current authority only."""
    started_at = active.formation_started_at
    completed_at = active.formation_completed_at
    persisted_duration = active.formation_duration_seconds
    if started_at is None or completed_at is None or persisted_duration is None:
        return None
    if completed_at != active.activated_at or completed_at < started_at:
        return None
    derived_duration = duration_seconds(started_at, completed_at)
    if persisted_duration != derived_duration:
        return None
    return started_at, completed_at, derived_duration


def active_mrz_order_key(active: ActiveMRZ) -> tuple[object, ...]:
    formation = current_formation_provenance(active)
    activation_recency = datetime.max.replace(tzinfo=timezone.utc) - (
        active.activated_at.astimezone(timezone.utc)
    )
    return (
        formation is None,
        formation[2] if formation is not None else Decimal("0"),
        activation_recency,
        active.symbol,
    )


def structural_location_label(value: str) -> str:
    labels = {
        "deep_discount_core_mrz": "Deep Discount",
        "shallow_discount_core_mrz": "Shallow Discount",
        "shallow_premium_core_mrz": "Shallow Premium",
        "deep_premium_core_mrz": "Deep Premium",
    }
    return labels[value]


@dataclass(frozen=True, slots=True)
class PostActivationState:
    status: str
    label: str
    reason: str
    direction: str
    direction_label: str


def classify_post_activation_state(
    total_observation_count: int,
    above_envelope_count: int,
    below_envelope_count: int,
) -> PostActivationState:
    """Interpret envelope activity without changing migration eligibility."""
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


def displacement_evidence(
    value: Decimal | None,
) -> tuple[str | None, str]:
    if value is None:
        return None, "No post-activation evidence"
    displayed_value = value.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    if displayed_value > 0:
        return "ABOVE", "Median displacement above midpoint"
    if displayed_value < 0:
        return "BELOW", "Median displacement below midpoint"
    return "CENTERED", "Centered around midpoint"


@dataclass(frozen=True, slots=True)
class DiagnosticSuccessorGroup:
    side: str
    side_label: str
    route: Route
    observations: tuple[Observation, ...]
    evaluation: ConcentrationEvaluation

    @property
    def newest_order_key(self) -> tuple[object, ...]:
        return self.observations[-1].order_key


def diagnostic_successor_groups(
    active: ActiveMRZ,
    post_activation: Sequence[Observation],
) -> tuple[DiagnosticSuccessorGroup, ...]:
    """Evaluate every external side/route pool without applying migration gates."""
    groups: list[DiagnosticSuccessorGroup] = []
    for route in Route:
        route_window = tuple(
            latest_route_window(
                tuple(item for item in post_activation if item.route is route)
            )
        )
        for side, side_label, predicate in (
            (
                "UP",
                "Higher",
                lambda item: item.observation_price > active.upper_migration_boundary,
            ),
            (
                "DOWN",
                "Lower",
                lambda item: item.observation_price < active.lower_migration_boundary,
            ),
        ):
            pool = tuple(item for item in route_window if predicate(item))
            if not pool:
                continue
            groups.append(
                DiagnosticSuccessorGroup(
                    side=side,
                    side_label=side_label,
                    route=route,
                    observations=pool,
                    evaluation=evaluate_concentration(pool, route),
                )
            )
    return tuple(groups)


def latest_diagnostic_group(
    groups: Sequence[DiagnosticSuccessorGroup],
) -> DiagnosticSuccessorGroup | None:
    return max(
        groups,
        key=lambda item: (
            item.newest_order_key,
            item.route.value,
            item.side,
        ),
        default=None,
    )


class MRZRobustnessService:
    """Build a read-only post-activation diagnostic from authoritative state."""

    def __init__(
        self,
        input_provider: RobustnessInputProvider,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._input_provider = input_provider
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def generate_report(self) -> dict[str, object]:
        active_mrzs, observations, migration_provenance = self._input_provider()
        generated_at = self._clock()
        observations_by_symbol: dict[str, list[Observation]] = {}
        for observation in observations:
            observations_by_symbol.setdefault(observation.symbol, []).append(observation)

        reports = [
            self.active_mrz_report(
                active,
                observations_by_symbol.get(active.symbol, []),
                generated_at,
                migration_provenance.get(
                    active.symbol,
                    {"has_migrated": False},
                ),
            )
            for active in sorted(active_mrzs, key=active_mrz_order_key)
        ]
        return {
            "generated_at": iso(generated_at),
            "active_mrz_count": len(reports),
            "lifecycle": [
                "Formation",
                "Activation",
                "Robustness Monitoring",
                "Migration Pressure",
                "Migration Confirmation",
            ],
            "active_mrzs": reports,
        }

    @staticmethod
    def _post_activation_observations(
        active: ActiveMRZ,
        observations: Sequence[Observation],
    ) -> tuple[Observation, ...]:
        ordered = tuple(sorted(observations, key=lambda item: item.order_key))
        activation = next(
            (
                item
                for item in ordered
                if item.event_id == active.activation_event_id
            ),
            None,
        )
        if activation is not None:
            return tuple(item for item in ordered if item.order_key > activation.order_key)
        return tuple(item for item in ordered if item.observed_at > active.activated_at)

    def active_mrz_report(
        self,
        active: ActiveMRZ,
        observations: Sequence[Observation],
        generated_at: datetime,
        migration: Mapping[str, object],
    ) -> dict[str, object]:
        formation = current_formation_provenance(active)
        post_activation = self._post_activation_observations(active, observations)
        total = len(post_activation)
        contained = sum(
            active.core_mrz_lower
            <= observation.observation_price
            <= active.core_mrz_upper
            for observation in post_activation
        )
        above_active_mrz = sum(
            observation.observation_price > active.core_mrz_upper
            for observation in post_activation
        )
        below_active_mrz = sum(
            observation.observation_price < active.core_mrz_lower
            for observation in post_activation
        )
        containment_percentage = (
            Decimal(contained) * Decimal("100") / Decimal(total)
            if total
            else None
        )

        upper_tests = sum(
            observation.observation_price >= active.core_mrz_upper
            for observation in post_activation
        )
        lower_tests = sum(
            observation.observation_price <= active.core_mrz_lower
            for observation in post_activation
        )
        above_upper_envelope = tuple(
            observation
            for observation in post_activation
            if observation.observation_price > active.upper_migration_boundary
        )
        below_lower_envelope = tuple(
            observation
            for observation in post_activation
            if observation.observation_price < active.lower_migration_boundary
        )
        outside_envelope = (*below_lower_envelope, *above_upper_envelope)
        post_activation_state = classify_post_activation_state(
            total,
            len(above_upper_envelope),
            len(below_lower_envelope),
        )
        pressure_status = post_activation_state.status
        pressure_label = post_activation_state.label
        pressure_reason = post_activation_state.reason
        pressure_direction = post_activation_state.direction
        pressure_direction_label = post_activation_state.direction_label

        midpoint_displacements = tuple(
            (observation.observation_price - active.core_mrz_midpoint)
            / active.ipda_width_at_activation
            * Decimal("100")
            for observation in post_activation
        )
        displacement_median = median_decimal(midpoint_displacements)
        displacement_direction, displacement_label = displacement_evidence(
            displacement_median
        )

        route_aligned = tuple(
            observation
            for observation in post_activation
            if observation.route is active.route_owner
        )
        structurally_aligned = tuple(
            observation
            for observation in route_aligned
            if classify_structural_location(
                active.route_owner,
                observation.observation_price,
                observation.ipda_20w_high,
                observation.ipda_20w_low,
            )
            is not None
        )
        if total == 0:
            route_integrity_status = "NO_POST_ACTIVATION_EVIDENCE"
            route_integrity_label = "No post-activation evidence"
        elif len(structurally_aligned) == total:
            route_integrity_status = "MAINTAINED"
            route_integrity_label = (
                "Discount structure maintained"
                if active.route_owner is Route.BTD
                else "Premium structure maintained"
            )
        else:
            route_integrity_status = "MIXED"
            route_integrity_label = "Mixed route structure observed"

        successor_groups = diagnostic_successor_groups(active, post_activation)
        qualifying_successor_groups = tuple(
            group
            for group in successor_groups
            if group.evaluation.result is ConcentrationResult.QUALIFIES
            and group.evaluation.cluster is not None
        )
        evaluated_successor_groups = tuple(
            group
            for group in successor_groups
            if len(group.observations) >= MIN_CLUSTER_OBSERVATIONS
        )
        successor_group = latest_diagnostic_group(qualifying_successor_groups)
        failed_successor_group = latest_diagnostic_group(evaluated_successor_groups)
        successor_candidate_detected = successor_group is not None

        if successor_candidate_detected:
            successor_status = "SUCCESSOR_CANDIDATE"
            successor_label = "Qualifying successor candidate"
            successor_reason = (
                "A canonical external concentration qualifies. The current MRZ "
                "remains authoritative until the production migration engine changes it."
            )
        elif failed_successor_group is not None:
            successor_status = "NO_QUALIFYING_SUCCESSOR"
            successor_label = "No qualifying successor"
            if (
                failed_successor_group.evaluation.result
                is ConcentrationResult.TOO_DISPERSED
            ):
                successor_reason = (
                    "External observations meet the minimum count but are too dispersed "
                    "for the production concentration allowance."
                )
            else:
                successor_reason = (
                    "External observations produced no structurally eligible qualifying "
                    "concentration."
                )
        elif outside_envelope:
            successor_status = "EXTERNAL_OBSERVATIONS"
            successor_label = "External observations detected"
            successor_reason = (
                "External observations exist, but no side-and-route pool has enough "
                "evidence for a qualifying concentration."
            )
        else:
            successor_status = "NO_SUCCESSOR_CANDIDATE"
            successor_label = "No successor candidate"
            successor_reason = "No qualifying external concentration exists."

        selected_successor_group = successor_group or failed_successor_group
        selected_evaluation = (
            selected_successor_group.evaluation
            if selected_successor_group is not None
            else None
        )
        selected_diagnostic = (
            selected_evaluation.diagnostic
            if selected_evaluation is not None
            else None
        )
        successor_cluster = (
            successor_group.evaluation.cluster
            if successor_group is not None
            else None
        )
        if successor_group is not None and successor_cluster is not None:
            candidate_lower = successor_cluster.lower
            candidate_upper = successor_cluster.upper
            successor_direction = successor_group.side
            successor_direction_label = successor_group.side_label
            successor_route = successor_group.route.value
            successor_evidence_count = successor_cluster.observation_count
            confirming_observation = max(
                successor_cluster.members,
                key=lambda item: item.order_key,
            )
            operational_migration_eligible = (
                build_successor_mrz(
                    active,
                    confirming_observation,
                    successor_cluster,
                )
                is not None
            )
            operational_migration_eligibility_label = (
                "Satisfied"
                if operational_migration_eligible
                else "Not satisfied"
            )
        else:
            candidate_lower = None
            candidate_upper = None
            successor_direction = None
            successor_direction_label = None
            successor_route = None
            successor_evidence_count = (
                len(selected_successor_group.observations)
                if selected_successor_group is not None
                else 0
            )
            operational_migration_eligible = None
            operational_migration_eligibility_label = "Not assessed"

        if total == 0:
            robustness_status = "NOT_YET_ASSESSABLE"
            robustness_label = "Not yet assessable"
            robustness_reason = "No post-activation observations are available yet."
        else:
            robustness_status = pressure_status
            robustness_label = pressure_label
            robustness_reason = pressure_reason

        location_label = structural_location_label(active.structural_location.value)
        structural_role_status = (
            "SUPPORTIVE" if active.route_owner is Route.BTD else "RESISTIVE"
        )
        structural_role_label = (
            "Supportive" if active.route_owner is Route.BTD else "Resistive"
        )
        successor_summary_status = (
            "CANDIDATE_DETECTED"
            if successor_candidate_detected
            else "NOT_DETECTED"
        )
        successor_summary_label = (
            "Candidate detected"
            if successor_candidate_detected
            else "Not detected"
        )
        if displacement_direction == "ABOVE":
            displacement_statement = (
                "Post-activation observations are centered above the active MRZ midpoint."
            )
        elif displacement_direction == "BELOW":
            displacement_statement = (
                "Post-activation observations are centered below the active MRZ midpoint."
            )
        elif displacement_direction == "CENTERED":
            displacement_statement = (
                "Post-activation observations are centered around the active MRZ midpoint."
            )
        else:
            displacement_statement = (
                "No post-activation displacement evidence is available yet."
            )
        if total == 0:
            summary_detail = (
                "No post-activation observations are available to assess behavior or "
                "successor formation."
            )
        elif pressure_direction == "UP":
            summary_detail = (
                "Above-envelope activity materially dominates. "
                + (
                    "A qualifying successor candidate is detected."
                    if successor_candidate_detected
                    else "No qualifying successor candidate is detected."
                )
            )
        elif pressure_direction == "DOWN":
            summary_detail = (
                "Below-envelope activity materially dominates. "
                + (
                    "A qualifying successor candidate is detected."
                    if successor_candidate_detected
                    else "No qualifying successor candidate is detected."
                )
            )
        elif pressure_label == "Two-sided / Consolidating":
            summary_detail = (
                "Post-activation observations are distributed on both sides of the active "
                "MRZ with no meaningful directional dominance. "
                + (
                    "A qualifying successor candidate is detected."
                    if successor_candidate_detected
                    else "No qualifying successor candidate is detected."
                )
            )
        else:
            summary_detail = (
                pressure_reason
                + " "
                + (
                    "A qualifying successor candidate is detected."
                    if successor_candidate_detected
                    else "No qualifying successor candidate is detected."
                )
            )

        return {
            "symbol": active.symbol,
            "route_owner": active.route_owner.value,
            "migration": dict(migration),
            "structural_authority": {
                "status": "AUTHORITATIVE",
                "label": "Authoritative",
                "structural_location": active.structural_location.value,
                "structural_location_label": location_label,
                "structural_role": structural_role_status,
                "structural_role_label": structural_role_label,
            },
            "active_mrz": {
                "lower": decimal_text(active.core_mrz_lower),
                "upper": decimal_text(active.core_mrz_upper),
                "midpoint": decimal_text(active.core_mrz_midpoint),
                "structural_location": active.structural_location.value,
                "activated_at": iso(active.activated_at),
                "activation_event_id": active.activation_event_id,
                "lower_migration_boundary": decimal_text(
                    active.lower_migration_boundary
                ),
                "upper_migration_boundary": decimal_text(
                    active.upper_migration_boundary
                ),
            },
            "formation_evidence": {
                "confirming_observation_count": active.confirming_observation_count,
                "started_at": iso(formation[0]) if formation is not None else None,
                "completed_at": iso(formation[1]) if formation is not None else None,
                "duration_seconds": (
                    decimal_text(formation[2]) if formation is not None else None
                ),
                "meaning": "Why the active MRZ was formed.",
            },
            "robustness_evidence": {
                "post_activation_observation_count": total,
                "meaning": "What occurred after the active MRZ was formed.",
            },
            "post_activation_robustness": {
                "status": robustness_status,
                "label": robustness_label,
                "reason": robustness_reason,
                "post_activation_observation_count": total,
            },
            "observation_position": {
                "above_active_mrz_observation_count": above_active_mrz,
                "inside_active_mrz_observation_count": contained,
                "below_active_mrz_observation_count": below_active_mrz,
                "total_observation_count": total,
                "definition": (
                    "Mutually exclusive post-activation observation counts relative "
                    "to the inclusive frozen active MRZ bounds."
                ),
            },
            "containment": {
                "inside_observation_count": contained,
                "total_observation_count": total,
                "percentage": decimal_text(containment_percentage),
            },
            "boundary_pressure": {
                "upper_boundary_test_count": upper_tests,
                "lower_boundary_test_count": lower_tests,
                "outside_envelope_observation_count": len(outside_envelope),
                "above_upper_envelope_observation_count": len(
                    above_upper_envelope
                ),
                "below_lower_envelope_observation_count": len(
                    below_lower_envelope
                ),
                "definition": (
                    "Boundary tests count observations at or beyond each frozen core "
                    "boundary. External observations fall beyond the migration envelope."
                ),
            },
            "mrz_displacement": {
                "median_signed_displacement_percentage_of_activation_ipda": decimal_text(
                    displacement_median
                ),
                "direction": displacement_direction,
                "label": displacement_label,
                "normalization": (
                    "Normalized by full IPDA 20W width stored at activation."
                ),
            },
            "route_integrity": {
                "status": route_integrity_status,
                "label": route_integrity_label,
                "route_aligned_observation_count": len(route_aligned),
                "structurally_aligned_observation_count": len(structurally_aligned),
                "opposite_route_observation_count": total - len(route_aligned),
                "total_observation_count": total,
            },
            "migration_pressure": {
                "status": pressure_status,
                "label": pressure_label,
                "reason": pressure_reason,
                "direction": pressure_direction,
                "direction_label": pressure_direction_label,
                "relevant_boundary_label": (
                    "Upper migration boundary"
                    if pressure_direction == "UP"
                    else "Lower migration boundary"
                    if pressure_direction == "DOWN"
                    else None
                ),
                "relevant_boundary": (
                    decimal_text(active.upper_migration_boundary)
                    if pressure_direction == "UP"
                    else decimal_text(active.lower_migration_boundary)
                    if pressure_direction == "DOWN"
                    else None
                ),
                "observations_beyond_envelope": len(outside_envelope),
                "above_upper_envelope_observation_count": len(
                    above_upper_envelope
                ),
                "below_lower_envelope_observation_count": len(
                    below_lower_envelope
                ),
                "current_mrz_remains_authoritative": True,
            },
            "successor_watch": {
                "status": successor_status,
                "label": successor_label,
                "reason": successor_reason,
                "symbol": active.symbol if successor_candidate_detected else None,
                "route": successor_route,
                "candidate_lower": decimal_text(candidate_lower),
                "candidate_upper": decimal_text(candidate_upper),
                "direction": successor_direction,
                "direction_label": successor_direction_label,
                "evidence_observation_count": successor_evidence_count,
                "required_observation_count": MIN_CLUSTER_OBSERVATIONS,
                "normalized_span": decimal_text(
                    selected_diagnostic.normalized_span
                    if selected_diagnostic is not None
                    else None
                ),
                "production_allowance": decimal_text(
                    CONCENTRATION_SPAN_THRESHOLD
                ),
                "production_evaluation_result": (
                    selected_evaluation.result.value
                    if selected_evaluation is not None
                    else ConcentrationResult.INSUFFICIENT_OBSERVATIONS.value
                ),
                "external_observation_count": len(outside_envelope),
                "higher_external_observation_count": len(above_upper_envelope),
                "lower_external_observation_count": len(below_lower_envelope),
                "operational_migration_eligible": operational_migration_eligible,
                "operational_migration_eligibility_label": (
                    operational_migration_eligibility_label
                ),
                "current_mrz_remains_authoritative": True,
                "diagnostic_only": True,
            },
            "mrz_age": {
                "activated_at": iso(active.activated_at),
                "active_duration_seconds": decimal_text(
                    duration_seconds(active.activated_at, generated_at)
                ),
            },
            "structural_summary": {
                "current_authority": (
                    f"{active.route_owner.value} · {location_label}"
                ),
                "robustness_status": robustness_status,
                "robustness_label": robustness_label,
                "pressure_direction": pressure_direction,
                "pressure_direction_label": pressure_direction_label,
                "structural_role": structural_role_status,
                "structural_role_label": structural_role_label,
                "successor_status": successor_summary_status,
                "successor_label": successor_summary_label,
                "authority_statement": (
                    f"The current {active.route_owner.value} MRZ remains authoritative."
                ),
                "displacement_statement": displacement_statement,
                "detail_statement": summary_detail,
            },
        }
