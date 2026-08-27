from __future__ import annotations

from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Callable, Mapping, Sequence

from app.concentration import ConcentrationResult, evaluate_concentration, latest_route_window
from app.domain import ActiveMRZ, Observation, Route
from app.state_engine import successor_eligible
from app.structure import classify_structural_location


RobustnessInputProvider = Callable[
    [],
    tuple[
        tuple[ActiveMRZ, ...],
        tuple[Observation, ...],
        Mapping[str, Mapping[str, object]],
    ],
]


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


def structural_location_label(value: str) -> str:
    labels = {
        "deep_discount_core_mrz": "Deep Discount",
        "shallow_discount_core_mrz": "Shallow Discount",
        "shallow_premium_core_mrz": "Shallow Premium",
        "deep_premium_core_mrz": "Deep Premium",
    }
    return labels[value]


def directional_evidence(
    upper_count: int,
    lower_count: int,
) -> tuple[str, str]:
    if upper_count > lower_count:
        return "UP", "Upward"
    if lower_count > upper_count:
        return "DOWN", "Downward"
    return "NEUTRAL", "Neutral"


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
            for active in sorted(active_mrzs, key=lambda item: item.symbol)
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
        post_activation = self._post_activation_observations(active, observations)
        total = len(post_activation)
        contained = sum(
            active.core_mrz_lower
            <= observation.observation_price
            <= active.core_mrz_upper
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
        pressure_direction, pressure_direction_label = directional_evidence(
            len(above_upper_envelope),
            len(below_lower_envelope),
        )

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

        owner_window = tuple(latest_route_window(route_aligned))
        successor_pool = tuple(
            observation
            for observation in owner_window
            if successor_eligible(active, observation)
        )
        successor_evaluation = evaluate_concentration(
            successor_pool,
            active.route_owner,
        )
        successor_confirmed = (
            successor_evaluation.result is ConcentrationResult.QUALIFIES
            and successor_evaluation.cluster is not None
        )
        if not successor_pool:
            successor_status = "NO_SUCCESSOR_CANDIDATE"
            successor_label = "No successor candidate"
        elif successor_confirmed:
            successor_status = "CONFIRMED_SUCCESSOR"
            successor_label = "Confirmed successor"
        elif len(successor_pool) >= 3:
            successor_status = "AWAITING_CONFIRMATION"
            successor_label = "Awaiting confirmation"
        else:
            successor_status = "CANDIDATE_FORMING"
            successor_label = "Candidate forming"

        diagnostic = successor_evaluation.diagnostic
        if successor_evaluation.cluster is not None:
            candidate_lower = successor_evaluation.cluster.lower
            candidate_upper = successor_evaluation.cluster.upper
        elif diagnostic.selected_lower is not None:
            candidate_lower = diagnostic.selected_lower
            candidate_upper = diagnostic.selected_upper
        elif successor_pool:
            candidate_lower = min(item.observation_price for item in successor_pool)
            candidate_upper = max(item.observation_price for item in successor_pool)
        else:
            candidate_lower = None
            candidate_upper = None

        if successor_pool and all(
            item.observation_price > active.upper_migration_boundary
            for item in successor_pool
        ):
            successor_direction = "UP"
            successor_direction_label = "Higher MRZ"
        elif successor_pool and all(
            item.observation_price < active.lower_migration_boundary
            for item in successor_pool
        ):
            successor_direction = "DOWN"
            successor_direction_label = "Lower MRZ"
        else:
            successor_direction = None
            successor_direction_label = None

        if total == 0:
            pressure_status = "NO_EVIDENCE"
            pressure_label = "No evidence"
            pressure_reason = (
                "No post-activation observations are available to assess migration pressure."
            )
        elif successor_confirmed:
            pressure_status = "MIGRATION_CANDIDATE"
            pressure_label = "Migration Candidate"
            pressure_reason = (
                "A same-route successor concentration satisfies the existing production "
                "confirmation rule. The persisted active MRZ remains authoritative."
            )
        elif outside_envelope:
            pressure_status = "UNDER_PRESSURE"
            pressure_label = "Under Pressure"
            pressure_reason = (
                "External observations were detected outside the active MRZ envelope. "
                "No successor MRZ is confirmed."
            )
        else:
            pressure_status = "STABLE"
            pressure_label = "Stable"
            pressure_reason = (
                "No post-activation observation has moved outside the active MRZ envelope."
            )

        if total == 0:
            robustness_status = "NOT_YET_ASSESSABLE"
            robustness_label = "Not yet assessable"
            robustness_reason = "No post-activation observations are available yet."
        elif pressure_status == "STABLE":
            robustness_status = "STABLE"
            robustness_label = "Stable"
            robustness_reason = (
                "No post-activation observation is beyond the active MRZ migration envelope."
            )
        else:
            robustness_status = "UNDER_PRESSURE"
            robustness_label = "Under Pressure"
            robustness_reason = (
                "Post-activation observations are present beyond the active MRZ migration envelope."
            )

        location_label = structural_location_label(active.structural_location.value)
        structural_role_status = (
            "SUPPORTIVE" if active.route_owner is Route.BTD else "RESISTIVE"
        )
        structural_role_label = (
            "Supportive" if active.route_owner is Route.BTD else "Resistive"
        )
        successor_summary_status = (
            "CONFIRMED" if successor_confirmed else "NOT_CONFIRMED"
        )
        successor_summary_label = (
            "Confirmed" if successor_confirmed else "Not confirmed"
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
                "No post-activation observations are available to assess pressure or "
                "successor formation."
            )
        elif pressure_direction == "UP":
            summary_detail = (
                "Post-activation observations are exerting upward pressure, but no "
                "successor MRZ is confirmed."
                if not successor_confirmed
                else "Upward evidence has produced a successor that satisfies the production check."
            )
        elif pressure_direction == "DOWN":
            summary_detail = (
                "Post-activation observations are exerting downward pressure, but no "
                "successor MRZ is confirmed."
                if not successor_confirmed
                else "Downward evidence has produced a successor that satisfies the production check."
            )
        elif outside_envelope:
            summary_detail = (
                "Post-activation observations are beyond both sides of the migration "
                "envelope without a dominant direction, but no successor MRZ is confirmed."
                if not successor_confirmed
                else "A successor satisfies the production check without a dominant pressure direction."
            )
        else:
            summary_detail = (
                "No post-activation observation is beyond the migration envelope, and "
                "no successor MRZ is confirmed."
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
                "started_at": iso(active.formation_started_at),
                "completed_at": iso(active.formation_completed_at),
                "duration_seconds": decimal_text(active.formation_duration_seconds),
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
                "symbol": active.symbol if successor_pool else None,
                "route": active.route_owner.value if successor_pool else None,
                "candidate_lower": decimal_text(candidate_lower),
                "candidate_upper": decimal_text(candidate_upper),
                "direction": successor_direction,
                "direction_label": successor_direction_label,
                "evidence_observation_count": len(successor_pool),
                "required_observation_count": diagnostic.minimum_required_count,
                "normalized_span": decimal_text(diagnostic.normalized_span),
                "production_evaluation_result": diagnostic.result.value,
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
