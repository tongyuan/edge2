from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any, Iterable, Mapping, Sequence

from app.activation_feasibility import (
    ALGORITHM_A,
    ActivationFeasibilityService,
    ClosestEvaluation,
    Scenario,
)
from app.concentration import (
    CONCENTRATION_SPAN_THRESHOLD,
    ConcentrationResult,
    MIN_CLUSTER_OBSERVATIONS,
    evaluate_concentration,
    latest_route_window,
)
from app.domain import ActiveMRZ, MRZEventType, Observation, Route, StructuralLocation
from app.state_engine import (
    build_successor_mrz,
    replay_symbol,
    successor_observation_pool,
)
from app.structure import classify_structural_location


MAX_CHECKPOINT = 8
MIN_DIAGNOSTIC_EPISODES = 8
MEANINGFUL_RATE_GAP = Decimal("0.15")
PRODUCTION_ALLOWANCE_PERCENT = Decimal("1.00")
TIGHT_NEAR_MISS_MAX_PERCENT = Decimal("1.50")
WIDER_NEAR_MISS_MAX_PERCENT = Decimal("2.00")


class Cohort(StrEnum):
    BTD_DEEP_DISCOUNT = "BTD_DEEP_DISCOUNT"
    BTD_SHALLOW_DISCOUNT = "BTD_SHALLOW_DISCOUNT"
    STR_DEEP_PREMIUM = "STR_DEEP_PREMIUM"
    STR_SHALLOW_PREMIUM = "STR_SHALLOW_PREMIUM"


class FormationCohort(StrEnum):
    PRODUCTION = "PRODUCTION"
    TIGHT_NEAR_MISS = "TIGHT_NEAR_MISS"
    WIDER_NEAR_MISS = "WIDER_NEAR_MISS"


COHORT_METADATA: dict[Cohort, dict[str, str]] = {
    Cohort.BTD_DEEP_DISCOUNT: {
        "label": "BTD · Deep Discount",
        "route": Route.BTD.value,
        "location": StructuralLocation.DEEP_DISCOUNT.value,
        "prior": "bottoming",
        "strategy_context": "discount_long",
        "hypothesis": "Activation itself may be structurally sufficient.",
        "candidate": "Immediate OPEN",
    },
    Cohort.BTD_SHALLOW_DISCOUNT: {
        "label": "BTD · Shallow Discount",
        "route": Route.BTD.value,
        "location": StructuralLocation.SHALLOW_DISCOUNT.value,
        "prior": "downside continuation risk",
        "strategy_context": "discount_long",
        "hypothesis": "Additional post-activation confirmation may be required.",
        "candidate": "WAIT for confirmation",
    },
    Cohort.STR_DEEP_PREMIUM: {
        "label": "STR · Deep Premium",
        "route": Route.STR.value,
        "location": StructuralLocation.DEEP_PREMIUM.value,
        "prior": "topping",
        "strategy_context": "premium_short",
        "hypothesis": "Activation itself may be structurally sufficient.",
        "candidate": "Immediate OPEN",
    },
    Cohort.STR_SHALLOW_PREMIUM: {
        "label": "STR · Shallow Premium",
        "route": Route.STR.value,
        "location": StructuralLocation.SHALLOW_PREMIUM.value,
        "prior": "upside continuation risk",
        "strategy_context": "premium_short",
        "hypothesis": "Additional post-activation confirmation may be required.",
        "candidate": "WAIT for confirmation",
    },
}


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
        stop = self.termination_index + 1 if self.termination_index is not None else len(self.source_observations)
        return self.source_observations[self.activation_index + 1 : stop]

    @property
    def ended_at(self) -> datetime | None:
        if self.termination_index is None:
            return None
        return self.source_observations[self.termination_index].observed_at

    @property
    def is_ongoing(self) -> bool:
        return self.termination_index is None

    @property
    def cohort(self) -> Cohort | None:
        return cohort_for(self.active_mrz)


@dataclass(frozen=True, slots=True)
class Reconstruction:
    episodes: tuple[Episode, ...]
    exclusions: tuple[dict[str, str], ...]


@dataclass(frozen=True, slots=True)
class FormationWindowCase:
    symbol: str
    route: Route
    cohort: FormationCohort
    source: str
    lower: Decimal
    upper: Decimal
    midpoint: Decimal
    anchor_observation: Observation
    post_anchor_observations: tuple[Observation, ...]
    minimum_required_allowance_pct: Decimal | None
    candidate_observation_count: int


def classify_formation_cohort(
    minimum_required_allowance_pct: Decimal,
) -> FormationCohort | None:
    if minimum_required_allowance_pct <= PRODUCTION_ALLOWANCE_PERCENT:
        return FormationCohort.PRODUCTION
    if minimum_required_allowance_pct <= TIGHT_NEAR_MISS_MAX_PERCENT:
        return FormationCohort.TIGHT_NEAR_MISS
    if minimum_required_allowance_pct <= WIDER_NEAR_MISS_MAX_PERCENT:
        return FormationCohort.WIDER_NEAR_MISS
    return None


def cohort_for(active: ActiveMRZ) -> Cohort | None:
    location = classify_structural_location(
        active.route_owner,
        active.core_mrz_midpoint,
        active.ipda_20w_high_at_activation,
        active.ipda_20w_low_at_activation,
    )
    mapping = {
        (Route.BTD, StructuralLocation.DEEP_DISCOUNT): Cohort.BTD_DEEP_DISCOUNT,
        (Route.BTD, StructuralLocation.SHALLOW_DISCOUNT): Cohort.BTD_SHALLOW_DISCOUNT,
        (Route.STR, StructuralLocation.DEEP_PREMIUM): Cohort.STR_DEEP_PREMIUM,
        (Route.STR, StructuralLocation.SHALLOW_PREMIUM): Cohort.STR_SHALLOW_PREMIUM,
    }
    return mapping.get((active.route_owner, location))


def reconstruct_episodes(
    observations: Iterable[Observation],
    *,
    minimum_required_count: int = MIN_CLUSTER_OBSERVATIONS,
    concentration_threshold: Decimal = CONCENTRATION_SPAN_THRESHOLD,
) -> Reconstruction:
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
            next_transition = transitions[transition_index + 1] if transition_index + 1 < len(transitions) else None
            termination_index = (
                by_event_id.get(next_transition.trigger_event_id) if next_transition is not None else None
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

            episode = Episode(
                symbol=symbol,
                generation=transition_index + 1,
                active_mrz=transition.new_mrz,
                activation_observation=ordered[activation_index],
                source_observations=ordered,
                activation_index=activation_index,
                termination_index=termination_index,
                termination_event_type=next_transition.event_type if next_transition else None,
                termination_event_id=next_transition.trigger_event_id if next_transition else None,
                migration_direction=migration_direction,
                outcome=outcome,
            )
            if episode.cohort is None:
                exclusions.append(
                    {
                        "symbol": symbol,
                        "activation_event_id": transition.trigger_event_id,
                        "reason": "route and activation structural location do not map to a valid cohort",
                    }
                )
                continue
            episodes.append(episode)

    return Reconstruction(tuple(episodes), tuple(exclusions))


def decimal_median(values: Sequence[Decimal]) -> Decimal | None:
    if not values:
        return None
    ordered = sorted(values)
    midpoint = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[midpoint]
    return (ordered[midpoint - 1] + ordered[midpoint]) / Decimal("2")


def signed_displacement(active: ActiveMRZ, observation: Observation) -> Decimal:
    return (
        observation.observation_price - active.core_mrz_midpoint
    ) / active.ipda_width_at_activation


def route_interpretation(route: Route, displacement: Decimal) -> str:
    if displacement == 0:
        return "NEUTRAL"
    supportive = displacement > 0 if route is Route.BTD else displacement < 0
    return "ROUTE_SUPPORTIVE" if supportive else "ROUTE_ADVERSE"


def containment(active: ActiveMRZ, observation: Observation) -> str:
    price = observation.observation_price
    if price < active.core_mrz_lower:
        return "BELOW_CORE"
    if price > active.core_mrz_upper:
        return "ABOVE_CORE"
    return "INSIDE_MRZ"


def raw_midpoint_direction(displacement: Decimal) -> str:
    if displacement > 0:
        return "ABOVE_MIDPOINT"
    if displacement < 0:
        return "BELOW_MIDPOINT"
    return "NEAR_MIDPOINT"


def envelope_position(active: ActiveMRZ, observation: Observation) -> str:
    if observation.observation_price > active.upper_migration_boundary:
        return "ABOVE_UPPER_ENVELOPE"
    if observation.observation_price < active.lower_migration_boundary:
        return "BELOW_LOWER_ENVELOPE"
    return "INSIDE_ENVELOPE"


def adverse_envelope_position(route: Route) -> str:
    return "BELOW_LOWER_ENVELOPE" if route is Route.BTD else "ABOVE_UPPER_ENVELOPE"


def checkpoint_observations(episode: Episode, checkpoint: int) -> tuple[Observation, ...] | None:
    if checkpoint == 0:
        return (episode.activation_observation,)
    post = episode.post_activation_observations
    if len(post) < checkpoint:
        return None
    return (episode.activation_observation, *post[:checkpoint])


def checkpoint_measurement(episode: Episode, checkpoint: int) -> dict[str, Any] | None:
    measured = checkpoint_observations(episode, checkpoint)
    if measured is None:
        return None
    active = episode.active_mrz
    current = measured[-1]
    displacements = [signed_displacement(active, item) for item in measured]
    median_displacement = decimal_median(displacements)
    assert median_displacement is not None
    envelope_counts = Counter(envelope_position(active, item) for item in measured)
    history_through_checkpoint = episode.source_observations[
        : episode.source_observations.index(current) + 1
    ]
    route_window = latest_route_window(
        tuple(
            item
            for item in history_through_checkpoint
            if item.route is current.route
        )
    )
    eligible_pool = successor_observation_pool(
        active,
        route_window,
        current,
    )
    evaluation = (
        evaluate_concentration(eligible_pool, current.route)
        if eligible_pool
        else None
    )
    candidate = (
        evaluation.cluster
        if evaluation is not None
        and evaluation.result is ConcentrationResult.QUALIFIES
        and evaluation.cluster is not None
        and build_successor_mrz(active, current, evaluation.cluster) is not None
        else None
    )
    return {
        "checkpoint": checkpoint_label(checkpoint),
        "checkpoint_index": checkpoint,
        "signed_median_displacement": median_displacement,
        "raw_direction": raw_midpoint_direction(median_displacement),
        "route_interpretation": route_interpretation(active.route_owner, median_displacement),
        "containment": containment(active, current),
        "upper_boundary_tests": sum(
            item.observation_price >= active.core_mrz_upper for item in measured
        ),
        "lower_boundary_tests": sum(
            item.observation_price <= active.core_mrz_lower for item in measured
        ),
        "above_upper_envelope": envelope_counts["ABOVE_UPPER_ENVELOPE"],
        "below_lower_envelope": envelope_counts["BELOW_LOWER_ENVELOPE"],
        "migration_pressure": pressure_direction(envelope_counts),
        "successor_eligible_observation_count": len(eligible_pool),
        "successor_minimum_required": MIN_CLUSTER_OBSERVATIONS,
        "successor_candidate": candidate is not None,
        "successor_candidate_lower": candidate.lower if candidate else None,
        "successor_candidate_upper": candidate.upper if candidate else None,
        "successor_candidate_normalized_span": candidate.normalized_span if candidate else None,
        "production_successor_evaluator_result": candidate is not None,
        "production_successor_evaluator_code": (
            evaluation.result.value if evaluation is not None else "NOT_EVALUATED"
        ),
    }


def pressure_direction(counts: Counter[str]) -> str:
    above = counts["ABOVE_UPPER_ENVELOPE"] > 0
    below = counts["BELOW_LOWER_ENVELOPE"] > 0
    if above and below:
        return "BOTH"
    if above:
        return "UPWARD"
    if below:
        return "DOWNWARD"
    return "NONE"


def checkpoint_label(checkpoint: int) -> str:
    return "Activation" if checkpoint == 0 else f"+{checkpoint}"


def available_checkpoints(episodes: Sequence[Episode]) -> range:
    maximum = max((len(item.post_activation_observations) for item in episodes), default=0)
    return range(0, max(4, min(MAX_CHECKPOINT, maximum)) + 1)


def aggregate_checkpoint(episodes: Sequence[Episode], checkpoint: int) -> dict[str, Any]:
    measurements = [
        measured
        for episode in episodes
        if (measured := checkpoint_measurement(episode, checkpoint)) is not None
    ]
    interpretations = Counter(item["route_interpretation"] for item in measurements)
    directions = Counter(item["raw_direction"] for item in measurements)
    containments = Counter(item["containment"] for item in measurements)
    pressure = Counter(item["migration_pressure"] for item in measurements)
    median = decimal_median([item["signed_median_displacement"] for item in measurements])
    return {
        "checkpoint": checkpoint_label(checkpoint),
        "checkpoint_index": checkpoint,
        "episodes_available": len(measurements),
        "signed_median_displacement": numeric(median),
        "above_midpoint": directions["ABOVE_MIDPOINT"],
        "below_midpoint": directions["BELOW_MIDPOINT"],
        "near_midpoint": directions["NEAR_MIDPOINT"],
        "route_supportive": interpretations["ROUTE_SUPPORTIVE"],
        "route_adverse": interpretations["ROUTE_ADVERSE"],
        "neutral": interpretations["NEUTRAL"],
        "inside_mrz": containments["INSIDE_MRZ"],
        "above_core": containments["ABOVE_CORE"],
        "below_core": containments["BELOW_CORE"],
        "upper_boundary_tests": sum(item["upper_boundary_tests"] for item in measurements),
        "lower_boundary_tests": sum(item["lower_boundary_tests"] for item in measurements),
        "observations_above_upper_envelope": sum(
            item["above_upper_envelope"] for item in measurements
        ),
        "observations_below_lower_envelope": sum(
            item["below_lower_envelope"] for item in measurements
        ),
        "episodes_with_upward_pressure": pressure["UPWARD"] + pressure["BOTH"],
        "episodes_with_downward_pressure": pressure["DOWNWARD"] + pressure["BOTH"],
        "successor_eligible_observation_count": sum(
            item["successor_eligible_observation_count"] for item in measurements
        ),
        "successor_minimum_required": MIN_CLUSTER_OBSERVATIONS,
        "episodes_with_successor_candidate": sum(
            item["successor_candidate"] for item in measurements
        ),
        "successor_candidates": [
            {
                "lower": numeric(item["successor_candidate_lower"]),
                "upper": numeric(item["successor_candidate_upper"]),
                "normalized_span": numeric(item["successor_candidate_normalized_span"]),
            }
            for item in measurements
            if item["successor_candidate"]
        ],
        "production_successor_evaluator_positive": sum(
            item["production_successor_evaluator_result"] for item in measurements
        ),
    }


def outcome_summary(episodes: Sequence[Episode]) -> dict[str, Any]:
    completed = [item for item in episodes if not item.is_ongoing]
    outcomes = Counter(item.outcome for item in completed)
    supportive = sum(
        migration_interpretation(item.active_mrz.route_owner, item.migration_direction)
        == "ROUTE_SUPPORTIVE"
        for item in completed
    )
    adverse = sum(
        migration_interpretation(item.active_mrz.route_owner, item.migration_direction)
        == "ROUTE_ADVERSE"
        for item in completed
    )
    duration_hours = [
        Decimal(str((item.ended_at - item.active_mrz.activated_at).total_seconds())) / Decimal("3600")
        for item in completed
        if item.ended_at is not None
    ]
    migration_observations = [
        Decimal(len(item.post_activation_observations))
        for item in completed
        if item.termination_event_type is MRZEventType.MIGRATED
    ]
    authoritative_counts = [Decimal(len(item.post_activation_observations)) for item in episodes]
    return {
        "completed": len(completed),
        "ongoing": sum(item.is_ongoing for item in episodes),
        "migrated_upward": outcomes["MIGRATED_UPWARD"],
        "migrated_downward": outcomes["MIGRATED_DOWNWARD"],
        "migrated_lateral": outcomes["MIGRATED_LATERAL"],
        "route_changed_or_replaced": outcomes["ROUTE_CHANGED_OR_REPLACED"],
        "route_supportive_migrations": supportive,
        "route_adverse_migrations": adverse,
        "median_hours_to_termination": numeric(decimal_median(duration_hours)),
        "median_observations_to_migration": numeric(decimal_median(migration_observations)),
        "median_authoritative_observation_count": numeric(decimal_median(authoritative_counts)),
    }


def migration_interpretation(route: Route, direction: str | None) -> str:
    if direction not in {"UPWARD", "DOWNWARD"}:
        return "NOT_APPLICABLE"
    supportive = direction == "UPWARD" if route is Route.BTD else direction == "DOWNWARD"
    return "ROUTE_SUPPORTIVE" if supportive else "ROUTE_ADVERSE"


def percentage_value(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return numeric(
        Decimal(numerator) * Decimal("100") / Decimal(denominator)
    )


def operator_outcome_language(cohort: Cohort) -> dict[str, str]:
    metadata = COHORT_METADATA[cohort]
    route = Route(metadata["route"])
    strategy_context = metadata["strategy_context"]
    strategy_label = strategy_context.replace("_", "-")
    location_label = {
        StructuralLocation.DEEP_DISCOUNT.value: "Deep Discount",
        StructuralLocation.SHALLOW_DISCOUNT.value: "Shallow Discount",
        StructuralLocation.SHALLOW_PREMIUM.value: "Shallow Premium",
        StructuralLocation.DEEP_PREMIUM.value: "Deep Premium",
    }[metadata["location"]]
    if route is Route.BTD:
        continuation_label = "Downside continuation"
        reversal_label = f"Upward reversal / {strategy_label} supportive"
        question = (
            f"After a BTD MRZ activates in {location_label}, is price more likely "
            "to continue lower or reverse upward?"
        )
        supportive_meaning = "Upward / supports BTD"
        adverse_meaning = "Downward / against BTD"
    else:
        continuation_label = "Upside continuation"
        reversal_label = f"Downward reversal / {strategy_label} supportive"
        question = (
            f"After an STR MRZ activates in {location_label}, is price more likely "
            "to continue higher or reverse downward?"
        )
        supportive_meaning = "Downward / supports STR"
        adverse_meaning = "Upward / against STR"
    return {
        "location_label": location_label,
        "question": question,
        "continuation_label": continuation_label,
        "reversal_label": reversal_label,
        "supportive_meaning": supportive_meaning,
        "adverse_meaning": adverse_meaning,
    }


def primary_outcome_summary(
    cohort: Cohort,
    episodes: Sequence[Episode],
) -> dict[str, Any]:
    language = operator_outcome_language(cohort)
    completed = tuple(item for item in episodes if not item.is_ongoing)
    supportive = sum(
        migration_interpretation(
            item.active_mrz.route_owner,
            item.migration_direction,
        )
        == "ROUTE_SUPPORTIVE"
        for item in completed
    )
    adverse = sum(
        migration_interpretation(
            item.active_mrz.route_owner,
            item.migration_direction,
        )
        == "ROUTE_ADVERSE"
        for item in completed
    )
    completed_count = len(completed)
    unresolved = sum(item.is_ongoing for item in episodes)
    other_terminal = completed_count - supportive - adverse
    sample_sufficient = completed_count >= MIN_DIAGNOSTIC_EPISODES
    if not sample_sufficient:
        bias = "UNESTABLISHED"
        sample_state = "INSUFFICIENT SAMPLE"
        research_status = "SAMPLE BUILDING"
    elif supportive > adverse:
        bias = "REVERSAL"
        sample_state = "DESCRIPTIVE SAMPLE"
        research_status = "PATTERN EMERGING"
    elif adverse > supportive:
        bias = "CONTINUATION"
        sample_state = "DESCRIPTIVE SAMPLE"
        research_status = "PATTERN EMERGING"
    else:
        bias = "MIXED"
        sample_state = "DESCRIPTIVE SAMPLE"
        research_status = "MIXED EVIDENCE"

    if completed_count == 0:
        qualification = (
            "No completed episodes. Outcome rates are not available yet."
        )
    elif completed_count == 1:
        qualification = (
            "Only 1 completed episode. Rates are descriptive and not "
            "statistically meaningful yet."
        )
    elif not sample_sufficient:
        qualification = (
            f"Only {completed_count} completed episodes. Rates are descriptive "
            "and not statistically meaningful yet."
        )
    else:
        qualification = (
            "Observed completed outcomes are descriptive research evidence, "
            "not a trading probability or recommendation."
        )

    return {
        **language,
        "completed_denominator": completed_count,
        "continuation_count": adverse,
        "continuation_percentage": percentage_value(adverse, completed_count),
        "reversal_count": supportive,
        "reversal_percentage": percentage_value(supportive, completed_count),
        "other_terminal_count": other_terminal,
        "unresolved_count": unresolved,
        "sample_sufficient": sample_sufficient,
        "sample_state": sample_state,
        "activation_outcome_bias": bias,
        "research_status": research_status,
        "qualification": qualification,
        "denominator_definition": (
            "Completed MRZ generations only; ongoing generations remain unresolved."
        ),
    }


def first_timing(episode: Episode, predicate: Any) -> tuple[int, Decimal] | None:
    for index, observation in enumerate(episode.post_activation_observations, 1):
        if predicate(index, observation):
            elapsed = Decimal(str((observation.observed_at - episode.active_mrz.activated_at).total_seconds()))
            return index, elapsed / Decimal("3600")
    return None


def episode_timings(episode: Episode) -> dict[str, tuple[int, Decimal] | None]:
    active = episode.active_mrz
    adverse_position = adverse_envelope_position(active.route_owner)
    individual = lambda observation: route_interpretation(  # noqa: E731
        active.route_owner, signed_displacement(active, observation)
    )

    def median_supportive(index: int, _observation: Observation) -> bool:
        measured = checkpoint_measurement(episode, index)
        return bool(measured and measured["route_interpretation"] == "ROUTE_SUPPORTIVE")

    def supportive_sequence(length: int, index: int) -> bool:
        if index < length:
            return False
        window = episode.post_activation_observations[index - length : index]
        return all(individual(item) == "ROUTE_SUPPORTIVE" for item in window)

    return {
        "first_route_supportive_displacement": first_timing(
            episode, lambda _index, item: individual(item) == "ROUTE_SUPPORTIVE"
        ),
        "first_route_supportive_median": first_timing(episode, median_supportive),
        "first_core_containment": first_timing(
            episode, lambda _index, item: containment(active, item) == "INSIDE_MRZ"
        ),
        "first_two_observation_supportive_sequence": first_timing(
            episode, lambda index, _item: supportive_sequence(2, index)
        ),
        "first_three_observation_supportive_sequence": first_timing(
            episode, lambda index, _item: supportive_sequence(3, index)
        ),
        "first_no_adverse_envelope_breach": first_timing(
            episode, lambda _index, item: envelope_position(active, item) != adverse_position
        ),
        "first_adverse_migration_pressure": first_timing(
            episode, lambda _index, item: envelope_position(active, item) == adverse_position
        ),
        "first_successor_candidate": first_timing(
            episode,
            lambda index, _item: bool(
                (measured := checkpoint_measurement(episode, index))
                and measured["successor_candidate"]
            ),
        ),
    }


def timing_summary(episodes: Sequence[Episode]) -> dict[str, Any]:
    collected: dict[str, list[tuple[int, Decimal]]] = defaultdict(list)
    for episode in episodes:
        for name, timing in episode_timings(episode).items():
            if timing is not None:
                collected[name].append(timing)
    return {
        name: {
            "episodes": len(values),
            "median_observation_index": numeric(
                decimal_median([Decimal(index) for index, _hours in values])
            ),
            "median_hours": numeric(decimal_median([hours for _index, hours in values])),
            "by_observation_index": {
                str(index): count for index, count in sorted(Counter(index for index, _ in values).items())
            },
        }
        for name, values in sorted(collected.items())
    }


def supportive_rate(checkpoint: Mapping[str, Any]) -> Decimal | None:
    denominator = int(checkpoint["episodes_available"])
    if not denominator:
        return None
    return Decimal(int(checkpoint["route_supportive"])) / Decimal(denominator)


def adverse_pressure_count(route: Route, checkpoint: Mapping[str, Any]) -> int:
    key = (
        "episodes_with_downward_pressure"
        if route is Route.BTD
        else "episodes_with_upward_pressure"
    )
    return int(checkpoint[key])


def candidate_confirmation_checkpoint(
    route: Route, checkpoints: Sequence[Mapping[str, Any]]
) -> int | None:
    baseline = supportive_rate(checkpoints[0]) if checkpoints else None
    if baseline is None:
        return None
    for checkpoint in checkpoints[1:]:
        denominator = int(checkpoint["episodes_available"])
        rate = supportive_rate(checkpoint)
        if denominator < MIN_DIAGNOSTIC_EPISODES or rate is None:
            continue
        pressure_rate = Decimal(adverse_pressure_count(route, checkpoint)) / Decimal(denominator)
        if rate >= Decimal("0.60") and rate - baseline >= MEANINGFUL_RATE_GAP and pressure_rate <= Decimal("0.20"):
            return int(checkpoint["checkpoint_index"])
    return None


def diagnose_cohort(
    cohort: Cohort,
    episodes: Sequence[Episode],
    checkpoints: Sequence[Mapping[str, Any]],
    outcomes: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    metadata = COHORT_METADATA[cohort]
    route = Route(metadata["route"])
    deep = cohort in {Cohort.BTD_DEEP_DISCOUNT, Cohort.STR_DEEP_PREMIUM}
    total = len(episodes)
    completed = int(outcomes["completed"])
    activation = checkpoints[0]
    activation_supportive = int(activation["route_supportive"])
    activation_adverse = int(activation["route_adverse"])
    candidate_checkpoint = None if deep else candidate_confirmation_checkpoint(route, checkpoints)

    supportive_evidence: list[str] = []
    contradictory_evidence: list[str] = []
    if total:
        supportive_evidence.append(
            f"{activation_supportive} / {total} episodes were route-supportive at activation."
        )
        if activation_adverse:
            contradictory_evidence.append(
                f"{activation_adverse} / {total} episodes were route-adverse at activation."
            )
    for checkpoint in checkpoints[1:5]:
        denominator = int(checkpoint["episodes_available"])
        if denominator:
            supportive_evidence.append(
                f"{checkpoint['route_supportive']} / {denominator} episodes were route-supportive at {checkpoint['checkpoint']}."
            )
            pressure_count = adverse_pressure_count(route, checkpoint)
            if pressure_count:
                contradictory_evidence.append(
                    f"{pressure_count} / {denominator} episodes had adverse envelope pressure by {checkpoint['checkpoint']}."
                )
    if completed:
        supportive_evidence.append(
            f"{outcomes['route_supportive_migrations']} / {completed} completed episodes ended in a route-supportive migration."
        )
        if outcomes["route_adverse_migrations"]:
            contradictory_evidence.append(
                f"{outcomes['route_adverse_migrations']} / {completed} completed episodes ended in a route-adverse migration."
            )

    limitation = (
        "Production successors are structure-first: either route may qualify on either "
        "external side when its own route/location rules pass."
    )
    if total < MIN_DIAGNOSTIC_EPISODES:
        status = "Insufficient sample"
        activation_answer = "No reliable conclusion can be drawn from activation alone."
        confirmation_answer = "The sample is too small to determine whether confirmation improves clarity."
        interpretation = "No trading-window policy discussion is supported yet."
    else:
        activation_rate = Decimal(activation_supportive) / Decimal(total)
        activation_adverse_rate = Decimal(activation_adverse) / Decimal(total)
        if activation_rate - activation_adverse_rate >= MEANINGFUL_RATE_GAP:
            status = "Pattern emerging"
            activation_answer = "Activation shows a descriptive route-supportive majority."
        elif activation_adverse_rate - activation_rate >= MEANINGFUL_RATE_GAP:
            status = "Candidate challenged"
            activation_answer = "Activation shows a descriptive route-adverse majority."
        else:
            status = "Mixed evidence"
            activation_answer = "Activation alone is mixed."

        later_rates = [
            (int(item["checkpoint_index"]), supportive_rate(item))
            for item in checkpoints[1:]
            if int(item["episodes_available"]) >= MIN_DIAGNOSTIC_EPISODES
        ]
        improving = [
            (index, rate)
            for index, rate in later_rates
            if rate is not None and rate - activation_rate >= MEANINGFUL_RATE_GAP
        ]
        if improving:
            best_index, _best_rate = max(improving, key=lambda item: (item[1], -item[0]))
            confirmation_answer = f"Post-activation evidence is descriptively clearer by +{best_index}."
        else:
            confirmation_answer = "No checkpoint shows a clear descriptive improvement over activation."
        interpretation = (
            "The immediate-OPEN hypothesis remains research-only."
            if deep
            else "The confirmation-required hypothesis remains research-only."
        )

    diagnosis = {
        "title": "Cohort Diagnosis",
        "status": status,
        "activation_alone": activation_answer,
        "confirmation_effect": confirmation_answer,
        "candidate_confirmation_point": (
            f"+{candidate_checkpoint} observations" if candidate_checkpoint is not None else "Not established"
        ),
        "supportive_evidence": supportive_evidence,
        "contradictory_evidence": contradictory_evidence or ["No contradictory event was observed in the available sample."],
        "interpretation": interpretation,
        "sample_assessment": f"Completed: {completed}; Ongoing: {outcomes['ongoing']}.",
        "limitations": [
            limitation,
            "Ongoing episodes contribute checkpoints but not completed outcomes.",
            "This is descriptive structure analysis; strategy P&L is intentionally excluded.",
        ],
    }
    policy = {
        "title": "Candidate Trading Window Policy",
        "strategy_context": metadata["strategy_context"],
        "candidate": metadata["candidate"],
        "candidate_checkpoint": (
            "Activation" if deep else (
                f"+{candidate_checkpoint} observations" if candidate_checkpoint is not None else "Not established"
            )
        ),
        "evidence_status": status,
        "production_status": "NOT APPROVED",
    }
    return diagnosis, policy


def cohort_report(cohort: Cohort, episodes: Sequence[Episode]) -> dict[str, Any]:
    checkpoints = [aggregate_checkpoint(episodes, index) for index in available_checkpoints(episodes)]
    outcomes = outcome_summary(episodes)
    diagnosis, policy = diagnose_cohort(cohort, episodes, checkpoints, outcomes)
    primary_outcome = primary_outcome_summary(cohort, episodes)
    confirmation_established = diagnosis["status"] != "Insufficient sample"
    completed = int(primary_outcome["completed_denominator"])
    if completed == 0:
        evidence_summary = "No completed episodes are available."
    elif completed < MIN_DIAGNOSTIC_EPISODES:
        evidence_summary = f"Insufficient completed episodes ({completed})."
    else:
        evidence_summary = f"{completed} completed episodes are available for description."
    return {
        "cohort": cohort.value,
        **COHORT_METADATA[cohort],
        "episode_counts": {
            "total": len(episodes),
            "completed": outcomes["completed"],
            "ongoing": outcomes["ongoing"],
            "unique_symbols": len({item.symbol for item in episodes}),
        },
        "research_question": primary_outcome["question"],
        "primary_outcome": primary_outcome,
        "operator_interpretation": {
            "structural_location": primary_outcome["location_label"],
            "strategy_context": COHORT_METADATA[cohort]["strategy_context"],
            "activation_outcome_bias": primary_outcome["activation_outcome_bias"],
            "current_evidence": evidence_summary,
            "confirmation_effect": (
                "DESCRIPTIVE PATTERN"
                if confirmation_established
                else "NOT ESTABLISHED"
            ),
            "research_status": primary_outcome["research_status"],
            "summary": (
                f"Insufficient evidence to determine whether a {COHORT_METADATA[cohort]['route']} "
                f"MRZ in {primary_outcome['location_label']} is more likely to produce "
                f"{primary_outcome['continuation_label'].lower()} or "
                f"{primary_outcome['reversal_label'].lower()} after activation."
                if not primary_outcome["sample_sufficient"]
                else (
                    f"The completed sample shows a descriptive "
                    f"{primary_outcome['activation_outcome_bias'].lower()} pattern."
                )
            ),
            "guardrail": (
                f"Do not infer that MRZ activation alone validates "
                f"{COHORT_METADATA[cohort]['strategy_context']}."
            ),
        },
        "candidate_confirmation_point": {
            "status": diagnosis["candidate_confirmation_point"],
            "evidence_status": diagnosis["status"],
            "confirmation_effect": diagnosis["confirmation_effect"],
            "production_status": "NOT APPROVED",
        },
        "episodes": [episode_record(item) for item in episodes],
        "checkpoints": checkpoints,
        "completed_episode_outcomes": outcomes,
        "first_confirmation_timing": timing_summary(episodes),
        "diagnosis": diagnosis,
        "candidate_policy": policy,
    }


def episode_record(episode: Episode) -> dict[str, Any]:
    active = episode.active_mrz
    timings = episode_timings(episode)
    adverse = timings["first_adverse_migration_pressure"]
    supportive = timings["first_route_supportive_displacement"]
    route_relative = migration_interpretation(
        active.route_owner,
        episode.migration_direction,
    )
    language = operator_outcome_language(episode.cohort)
    route_relative_meaning = {
        "ROUTE_SUPPORTIVE": language["supportive_meaning"],
        "ROUTE_ADVERSE": language["adverse_meaning"],
        "NOT_APPLICABLE": "Unresolved or non-directional terminal outcome",
    }[route_relative]
    return {
        "symbol": episode.symbol,
        "generation": episode.generation,
        "route": active.route_owner.value,
        "activated_at": iso(active.activated_at),
        "mrz_lower": numeric(active.core_mrz_lower),
        "mrz_upper": numeric(active.core_mrz_upper),
        "mrz_midpoint": numeric(active.core_mrz_midpoint),
        "ipda_20w_high_at_activation": numeric(active.ipda_20w_high_at_activation),
        "ipda_20w_low_at_activation": numeric(active.ipda_20w_low_at_activation),
        "structural_location_at_activation": active.structural_location.value,
        "activation_event_id": active.activation_event_id,
        "post_activation_observations": len(episode.post_activation_observations),
        "ended_at": iso(episode.ended_at),
        "status": "ONGOING" if episode.is_ongoing else "COMPLETED",
        "terminal_event": (
            episode.termination_event_type.value
            if episode.termination_event_type is not None
            else None
        ),
        "outcome": episode.outcome,
        "migration_direction": episode.migration_direction,
        "route_relative_migration": route_relative,
        "route_relative_meaning": route_relative_meaning,
        "first_supportive_observation": supportive[0] if supportive else None,
        "first_supportive_hours": numeric(supportive[1]) if supportive else None,
        "first_adverse_pressure_observation": adverse[0] if adverse else None,
        "first_adverse_pressure_hours": numeric(adverse[1]) if adverse else None,
    }


def checkpoint_by_index(report: Mapping[str, Any], index: int) -> Mapping[str, Any] | None:
    return next(
        (item for item in report["checkpoints"] if item["checkpoint_index"] == index),
        None,
    )


def cross_route_diagnosis(
    route: Route, deep: Mapping[str, Any], shallow: Mapping[str, Any]
) -> dict[str, Any]:
    comparable_at: str = "Not established"
    deep_activation = checkpoint_by_index(deep, 0)
    deep_rate = supportive_rate(deep_activation) if deep_activation else None
    if deep_rate is not None and int(deep_activation["episodes_available"]) >= MIN_DIAGNOSTIC_EPISODES:
        for checkpoint in shallow["checkpoints"][1:]:
            rate = supportive_rate(checkpoint)
            if (
                rate is not None
                and int(checkpoint["episodes_available"]) >= MIN_DIAGNOSTIC_EPISODES
                and abs(rate - deep_rate) <= Decimal("0.10")
            ):
                comparable_at = checkpoint["checkpoint"]
                break
    enough = (
        deep["episode_counts"]["total"] >= MIN_DIAGNOSTIC_EPISODES
        and shallow["episode_counts"]["total"] >= MIN_DIAGNOSTIC_EPISODES
    )
    if not enough:
        interpretation = "Insufficient paired sample to compare Deep and Shallow confirmation burden."
    elif comparable_at == "Not established":
        interpretation = "Shallow behavior does not become descriptively comparable to Deep behavior at an observed checkpoint."
    elif comparable_at == "+1":
        interpretation = "Deep location does not show a clearly lower descriptive confirmation burden."
    else:
        interpretation = f"Shallow behavior first resembles Deep activation around {comparable_at}."
    return {
        "route": route.value,
        "deep_cohort": deep["label"],
        "shallow_cohort": shallow["label"],
        "shallow_comparable_checkpoint": comparable_at,
        "interpretation": interpretation,
    }


def cross_cohort_diagnosis(reports: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    by_cohort = {item["cohort"]: item for item in reports}
    btd = cross_route_diagnosis(
        Route.BTD,
        by_cohort[Cohort.BTD_DEEP_DISCOUNT.value],
        by_cohort[Cohort.BTD_SHALLOW_DISCOUNT.value],
    )
    st_r = cross_route_diagnosis(
        Route.STR,
        by_cohort[Cohort.STR_DEEP_PREMIUM.value],
        by_cohort[Cohort.STR_SHALLOW_PREMIUM.value],
    )
    if "Insufficient" in btd["interpretation"] or "Insufficient" in st_r["interpretation"]:
        overall = "The current sample is insufficient to determine whether Deep location materially reduces confirmation burden."
        status = "Insufficient sample"
    elif btd["shallow_comparable_checkpoint"] == "+1" and st_r["shallow_comparable_checkpoint"] == "+1":
        overall = "The current descriptive sample does not show a lower confirmation burden for Deep location."
        status = "Candidate challenged"
    else:
        overall = "Deep and Shallow behavior differ descriptively, but the comparison remains research-only."
        status = "Pattern emerging"
    return {
        "title": "Cross-Cohort Diagnosis",
        "status": status,
        "BTD": btd,
        "STR": st_r,
        "overall_interpretation": overall,
    }


def audit_reconciliation(
    observations: Sequence[Observation],
    event_rows: Sequence[Mapping[str, Any]],
    active_rows: Sequence[ActiveMRZ],
) -> dict[str, Any]:
    by_symbol: dict[str, list[Observation]] = defaultdict(list)
    for observation in observations:
        by_symbol[observation.symbol].append(observation)
    expected_events: set[tuple[str, int, str, str]] = set()
    expected_active: dict[str, str] = {}
    for symbol, rows in by_symbol.items():
        replay = replay_symbol(rows)
        expected_events.update(
            (
                transition.symbol,
                transition.sequence,
                transition.event_type.value,
                transition.trigger_event_id,
            )
            for transition in replay.transitions
        )
        if replay.active_mrz is not None:
            expected_active[symbol] = replay.active_mrz.activation_event_id
    persisted_events = {
        (str(row["symbol"]), int(row["sequence"]), str(row["event_type"]), str(row["trigger_event_id"]))
        for row in event_rows
    }
    persisted_active = {row.symbol: row.activation_event_id for row in active_rows}
    event_match = expected_events == persisted_events
    active_match = expected_active == persisted_active
    return {
        "persisted_event_rows": len(persisted_events),
        "reconstructed_event_rows": len(expected_events),
        "event_history_matches_replay": event_match,
        "active_state_matches_replay": active_match,
        "fully_reconstructable": event_match and active_match,
        "limitations": [
            message
            for condition, message in (
                (
                    not event_match,
                    "Persisted mrz_events do not match deterministic replay; unmatched generations require investigation.",
                ),
                (
                    not active_match,
                    "Persisted active_mrz rows do not match deterministic replay.",
                ),
            )
            if condition
        ],
    }


def overall_diagnosis(reports: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    summaries = []
    for report in reports:
        policy = report["candidate_policy"]
        summaries.append(
            {
                "cohort": report["label"],
                "hypothesis": policy["candidate"],
                "status": policy["evidence_status"],
                "candidate_checkpoint": policy["candidate_checkpoint"],
            }
        )
    return {
        "title": "Trading Window Research Diagnosis",
        "cohorts": summaries,
        "production_recommendation": "No rule promoted. Continue sampling.",
    }


def _formation_case_from_episode(episode: Episode) -> FormationWindowCase:
    active = episode.active_mrz
    return FormationWindowCase(
        symbol=episode.symbol,
        route=active.route_owner,
        cohort=FormationCohort.PRODUCTION,
        source="AUTHORITATIVE_MRZ",
        lower=active.core_mrz_lower,
        upper=active.core_mrz_upper,
        midpoint=active.core_mrz_midpoint,
        anchor_observation=episode.activation_observation,
        post_anchor_observations=episode.post_activation_observations,
        minimum_required_allowance_pct=None,
        candidate_observation_count=active.confirming_observation_count,
    )


def _near_miss_case(
    *,
    symbol: str,
    route: Route,
    source: str,
    evaluation: ClosestEvaluation,
    route_observations: Sequence[Observation],
    symbol_observations: Sequence[Observation],
) -> FormationWindowCase | None:
    required = evaluation.minimum_required_allowance_pct
    cohort = classify_formation_cohort(required)
    if cohort not in {
        FormationCohort.TIGHT_NEAR_MISS,
        FormationCohort.WIDER_NEAR_MISS,
    }:
        return None
    if evaluation.structural_eligibility_passed is not True:
        return None
    anchor = route_observations[evaluation.ordinal - 1]
    if anchor.observed_at != evaluation.timestamp:
        raise RuntimeError("candidate ordinal and timestamp do not identify the same observation")
    return FormationWindowCase(
        symbol=symbol,
        route=route,
        cohort=cohort,
        source=source,
        lower=evaluation.candidate_lower_boundary,
        upper=evaluation.candidate_upper_boundary,
        midpoint=(
            evaluation.candidate_lower_boundary
            + evaluation.candidate_upper_boundary
        )
        / Decimal("2"),
        anchor_observation=anchor,
        post_anchor_observations=tuple(
            item for item in symbol_observations if item.order_key > anchor.order_key
        ),
        minimum_required_allowance_pct=required,
        candidate_observation_count=evaluation.candidate_observation_count,
    )


def reconstruct_near_miss_cases(
    observations: Sequence[Observation],
) -> tuple[FormationWindowCase, ...]:
    """Reconstruct exact current/closest production near misses without state writes."""
    by_symbol: dict[str, list[Observation]] = defaultdict(list)
    by_symbol_route: dict[tuple[str, Route], list[Observation]] = defaultdict(list)
    for observation in observations:
        by_symbol[observation.symbol].append(observation)
        by_symbol_route[(observation.symbol, observation.route)].append(observation)
    ordered_symbols = {
        symbol: tuple(sorted(rows, key=lambda item: item.order_key))
        for symbol, rows in by_symbol.items()
    }
    production_scenario = Scenario(
        ALGORITHM_A,
        MIN_CLUSTER_OBSERVATIONS,
        CONCENTRATION_SPAN_THRESHOLD,
    )
    cases_by_key: dict[
        tuple[str, Route, datetime, Decimal, Decimal, Decimal],
        tuple[FormationWindowCase, set[str]],
    ] = {}
    for (symbol, route), rows in sorted(
        by_symbol_route.items(),
        key=lambda item: (item[0][0], item[0][1].value),
    ):
        ordered_route = tuple(sorted(rows, key=lambda item: item.order_key))
        outcome = ActivationFeasibilityService.evaluate_sequence(
            ordered_route,
            production_scenario,
        )
        if not outcome.eligible or outcome.activated:
            continue
        for source, evaluation in (
            ("HISTORICAL_CLOSEST", outcome.closest_evaluation),
            ("CURRENT", outcome.current_evaluation),
        ):
            if evaluation is None:
                continue
            case = _near_miss_case(
                symbol=symbol,
                route=route,
                source=source,
                evaluation=evaluation,
                route_observations=ordered_route,
                symbol_observations=ordered_symbols[symbol],
            )
            if case is None or case.minimum_required_allowance_pct is None:
                continue
            key = (
                case.symbol,
                case.route,
                case.anchor_observation.observed_at,
                case.lower,
                case.upper,
                case.minimum_required_allowance_pct,
            )
            if key in cases_by_key:
                cases_by_key[key][1].add(source)
            else:
                cases_by_key[key] = (case, {source})

    cases = []
    for case, sources in cases_by_key.values():
        scope = (
            "CURRENT_AND_HISTORICAL_CLOSEST"
            if sources == {"CURRENT", "HISTORICAL_CLOSEST"}
            else next(iter(sources))
        )
        cases.append(
            FormationWindowCase(
                symbol=case.symbol,
                route=case.route,
                cohort=case.cohort,
                source=scope,
                lower=case.lower,
                upper=case.upper,
                midpoint=case.midpoint,
                anchor_observation=case.anchor_observation,
                post_anchor_observations=case.post_anchor_observations,
                minimum_required_allowance_pct=case.minimum_required_allowance_pct,
                candidate_observation_count=case.candidate_observation_count,
            )
        )
    return tuple(
        sorted(
            cases,
            key=lambda item: (
                item.cohort.value,
                item.minimum_required_allowance_pct or Decimal("0"),
                item.symbol,
                item.route.value,
                item.anchor_observation.order_key,
            ),
        )
    )


def formation_case_timings(
    case: FormationWindowCase,
) -> dict[str, tuple[int, Decimal] | None]:
    collected: dict[str, tuple[int, Decimal] | None] = {
        "first_supportive": None,
        "first_adverse": None,
    }
    for index, observation in enumerate(case.post_anchor_observations, 1):
        displacement = (
            observation.observation_price - case.midpoint
        ) / case.anchor_observation.ipda_width
        interpretation = route_interpretation(case.route, displacement)
        elapsed = Decimal(
            str(
                (
                    observation.observed_at
                    - case.anchor_observation.observed_at
                ).total_seconds()
            )
        ) / Decimal("3600")
        if (
            interpretation == "ROUTE_SUPPORTIVE"
            and collected["first_supportive"] is None
        ):
            collected["first_supportive"] = (index, elapsed)
        if (
            interpretation == "ROUTE_ADVERSE"
            and collected["first_adverse"] is None
        ):
            collected["first_adverse"] = (index, elapsed)
    return collected


def formation_case_record(case: FormationWindowCase) -> dict[str, Any]:
    timings = formation_case_timings(case)
    supportive = timings["first_supportive"]
    adverse = timings["first_adverse"]
    if not case.post_anchor_observations:
        outcome = "PENDING_FOLLOW_THROUGH"
        outcome_label = "Pending follow-through"
    elif supportive is not None and (
        adverse is None or supportive[0] < adverse[0]
    ):
        outcome = "SUPPORTIVE_FIRST"
        outcome_label = "Supportive behavior arrived first"
    elif adverse is not None and (
        supportive is None or adverse[0] < supportive[0]
    ):
        outcome = "ADVERSE_FIRST"
        outcome_label = "Adverse behavior arrived first"
    else:
        outcome = "UNRESOLVED"
        outcome_label = "Post-anchor evidence unresolved"

    supportive_window_hours: Decimal | None = None
    supportive_window_censored = False
    if outcome == "SUPPORTIVE_FIRST" and supportive is not None:
        supportive_observation = case.post_anchor_observations[supportive[0] - 1]
        if adverse is not None:
            end = case.post_anchor_observations[adverse[0] - 1].observed_at
        else:
            end = case.post_anchor_observations[-1].observed_at
            supportive_window_censored = True
        supportive_window_hours = Decimal(
            str((end - supportive_observation.observed_at).total_seconds())
        ) / Decimal("3600")

    labels = {
        FormationCohort.PRODUCTION: "Production",
        FormationCohort.TIGHT_NEAR_MISS: "Tight near miss",
        FormationCohort.WIDER_NEAR_MISS: "Wider near miss",
    }
    return {
        "symbol": case.symbol,
        "route": case.route.value,
        "cohort": case.cohort.value,
        "candidate_class": labels[case.cohort],
        "source": case.source,
        "is_active_mrz": case.cohort is FormationCohort.PRODUCTION,
        "production_allowance_pct": numeric(PRODUCTION_ALLOWANCE_PERCENT),
        "minimum_required_allowance_pct": numeric(
            case.minimum_required_allowance_pct
        ),
        "candidate_lower": numeric(case.lower),
        "candidate_upper": numeric(case.upper),
        "candidate_midpoint": numeric(case.midpoint),
        "candidate_observation_count": case.candidate_observation_count,
        "anchor_at": iso(case.anchor_observation.observed_at),
        "anchor_label": (
            "Activated"
            if case.cohort is FormationCohort.PRODUCTION
            else "Candidate observed"
        ),
        "post_anchor_observations": len(case.post_anchor_observations),
        "has_follow_through": bool(case.post_anchor_observations),
        "first_supportive_observation": supportive[0] if supportive else None,
        "first_supportive_hours": numeric(supportive[1]) if supportive else None,
        "first_adverse_observation": adverse[0] if adverse else None,
        "first_adverse_hours": numeric(adverse[1]) if adverse else None,
        "supportive_window_hours": numeric(supportive_window_hours),
        "supportive_window_censored": supportive_window_censored,
        "outcome": outcome,
        "outcome_label": outcome_label,
    }


def _ordinal_distribution(
    records: Sequence[Mapping[str, Any]], key: str
) -> dict[str, int]:
    return {
        str(index): count
        for index, count in sorted(
            Counter(
                int(record[key])
                for record in records
                if record[key] is not None
            ).items()
        )
    }


def _formation_cohort_summary(
    cohort: FormationCohort,
    records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    follow_through = [item for item in records if item["has_follow_through"]]
    supportive_first = [
        item for item in records if item["outcome"] == "SUPPORTIVE_FIRST"
    ]
    adverse_first = [
        item for item in records if item["outcome"] == "ADVERSE_FIRST"
    ]
    pending = [
        item for item in records if item["outcome"] == "PENDING_FOLLOW_THROUGH"
    ]
    resolved = len(supportive_first) + len(adverse_first)
    unresolved = len(records) - resolved
    supportive_lags = [
        Decimal(str(item["first_supportive_hours"]))
        for item in records
        if item["first_supportive_hours"] is not None
    ]
    adverse_lags = [
        Decimal(str(item["first_adverse_hours"]))
        for item in records
        if item["first_adverse_hours"] is not None
    ]
    labels = {
        FormationCohort.PRODUCTION: "≤1.00% Production",
        FormationCohort.TIGHT_NEAR_MISS: "1.00–1.50% Near Miss",
        FormationCohort.WIDER_NEAR_MISS: "1.50–2.00% Near Miss",
    }
    return {
        "cohort": cohort.value,
        "label": labels[cohort],
        "candidates": len(records),
        "with_follow_through": len(follow_through),
        "resolved": resolved,
        "pending": len(pending),
        "unresolved": unresolved,
        "supportive_first": {
            "numerator": len(supportive_first),
            "denominator": resolved,
            "percentage": percentage_value(len(supportive_first), resolved),
        },
        "adverse_first": {
            "numerator": len(adverse_first),
            "denominator": resolved,
            "percentage": percentage_value(len(adverse_first), resolved),
        },
        "median_supportive_lag_hours": numeric(decimal_median(supportive_lags)),
        "median_adverse_lag_hours": numeric(decimal_median(adverse_lags)),
        "supportive_ordinal_distribution": _ordinal_distribution(
            records, "first_supportive_observation"
        ),
        "adverse_ordinal_distribution": _ordinal_distribution(
            records, "first_adverse_observation"
        ),
        "supportive_first_windows": {
            "numerator": len(supportive_first),
            "denominator": resolved,
        },
        "sample_state": (
            "PRELIMINARY"
            if resolved < MIN_DIAGNOSTIC_EPISODES
            else "DESCRIPTIVE SAMPLE"
        ),
    }


def _formation_interpretation(
    summaries: Sequence[Mapping[str, Any]],
) -> dict[str, str]:
    by_cohort = {item["cohort"]: item for item in summaries}
    production = by_cohort[FormationCohort.PRODUCTION.value]
    near = [
        by_cohort[FormationCohort.TIGHT_NEAR_MISS.value],
        by_cohort[FormationCohort.WIDER_NEAR_MISS.value],
    ]
    if int(production["resolved"]) < MIN_DIAGNOSTIC_EPISODES or any(
        int(item["resolved"]) < MIN_DIAGNOSTIC_EPISODES for item in near
    ):
        return {
            "status": "Preliminary",
            "text": (
                "The current sample is insufficient to determine whether near-miss "
                "candidates provide trading windows comparable to production MRZs."
            ),
        }

    production_rate = Decimal(
        str(production["supportive_first"]["percentage"])
    )
    statements = []
    for item in near:
        rate = Decimal(str(item["supportive_first"]["percentage"]))
        gap = rate - production_rate
        if abs(gap) <= Decimal("15"):
            statements.append(
                f"{item['label']} showed supportive-first behavior at a rate "
                "similar to production MRZs in the current sample."
            )
        elif gap > 0:
            statements.append(
                f"{item['label']} showed supportive-first behavior more often "
                "than production MRZs in the current sample."
            )
        else:
            statements.append(
                f"{item['label']} showed adverse-first behavior more often than "
                "production MRZs in the current sample."
            )
    return {"status": "Descriptive evidence", "text": " ".join(statements)}


def formation_strictness_comparison(
    observations: Sequence[Observation],
    production_episodes: Sequence[Episode],
) -> dict[str, Any]:
    cases = [
        *(_formation_case_from_episode(item) for item in production_episodes),
        *reconstruct_near_miss_cases(observations),
    ]
    records = [formation_case_record(item) for item in cases]
    summaries = []
    route_summaries: dict[str, list[dict[str, Any]]] = {
        Route.BTD.value: [],
        Route.STR.value: [],
    }
    for cohort in FormationCohort:
        cohort_records = [item for item in records if item["cohort"] == cohort.value]
        summaries.append(_formation_cohort_summary(cohort, cohort_records))
        for route in Route:
            route_summaries[route.value].append(
                _formation_cohort_summary(
                    cohort,
                    [item for item in cohort_records if item["route"] == route.value],
                )
            )
    return {
        "title": "Production vs Near-Miss Windows",
        "research_question": (
            "After the structural candidate appears, does supportive behavior tend "
            "to arrive before adverse behavior?"
        ),
        "cohort_definitions": {
            FormationCohort.PRODUCTION.value: "minimum allowance required ≤ 1.00%; authoritative production MRZ",
            FormationCohort.TIGHT_NEAR_MISS.value: "minimum allowance required > 1.00% and ≤ 1.50%",
            FormationCohort.WIDER_NEAR_MISS.value: "minimum allowance required > 1.50% and ≤ 2.00%",
            "EXCLUDED": "minimum allowance required > 2.00%",
        },
        "follow_through_definition": (
            "At least one canonical symbol observation strictly after the activation "
            "or candidate anchor."
        ),
        "outcome_denominator": (
            "Supportive-first and adverse-first percentages use resolved cases only; "
            "pending and unresolved cases remain visible and excluded from the rate."
        ),
        "summaries": summaries,
        "by_route": route_summaries,
        "cases": records,
        "near_miss_details": [
            item for item in records if not item["is_active_mrz"]
        ],
        "evidence_interpretation": _formation_interpretation(summaries),
        "invariants": {
            "candidate_geometry": "actual evaluator-selected bounds; never widened to a cohort ceiling",
            "candidate_anchor": "candidate observed_at; never labeled as activation",
            "production_state": "read-only; no active MRZ or MRZ event is created",
            "classifier": "shared BTD/STR route_interpretation semantics",
        },
    }


def build_feasibility_report(
    observations: Sequence[Observation],
    event_rows: Sequence[Mapping[str, Any]] = (),
    active_rows: Sequence[ActiveMRZ] = (),
) -> dict[str, Any]:
    reconstruction = reconstruct_episodes(observations)
    grouped = {
        cohort: [item for item in reconstruction.episodes if item.cohort is cohort]
        for cohort in Cohort
    }
    reports = [cohort_report(cohort, grouped[cohort]) for cohort in Cohort]
    production_vs_near_miss = formation_strictness_comparison(
        observations,
        reconstruction.episodes,
    )
    reconciliation = audit_reconciliation(observations, event_rows, active_rows)
    completed = sum(not item.is_ongoing for item in reconstruction.episodes)
    ongoing = sum(item.is_ongoing for item in reconstruction.episodes)
    data_as_of = max((item.observed_at for item in observations), default=None)
    return {
        "title": "MRZ Trading Window Feasibility",
        "introduction": (
            "Tests whether route + structural location + post-activation MRZ behavior can support "
            "a defensible future WAIT / OPEN timing policy."
        ),
        "mode": "Measurement and diagnosis only. No production trading-window behavior is changed.",
        "data_as_of": iso(data_as_of),
        "sampling_unit": "MRZ activation episode (one MRZ generation), not symbol",
        "reconstruction": {
            "total_episodes": len(reconstruction.episodes),
            "completed_episodes": completed,
            "ongoing_episodes": ongoing,
            "excluded_episodes": len(reconstruction.exclusions),
            "exclusions": list(reconstruction.exclusions),
            **reconciliation,
        },
        "methodology": {
            "episode": "one MRZ generation and lifecycle; multiple generations of one symbol remain separate episodes",
            "completed_episode": "an MRZ generation that reached a canonical terminal transition",
            "ongoing_episode": "an active unresolved generation; excluded from final continuation/reversal rates",
            "unique_symbol_breadth": "distinct symbols represented in a cohort, reported separately from generation count",
            "chronology": "observed_at, then received_at, then persisted row id; event IDs are never chronology",
            "post_activation_selection": (
                "all persisted symbol observations after the activation trigger through and including the "
                "authoritative termination trigger; ongoing episodes end at available history"
            ),
            "checkpoint_series": (
                "cumulative activation observation plus the first N authoritative post-activation observations; +N never means bars"
            ),
            "route_supportive": "movement or terminal direction consistent with the current route owner",
            "route_adverse": "movement or terminal direction inconsistent with the current route owner",
            "near_miss_candidate": (
                "the exact structurally eligible Algorithm A / four-observation candidate "
                "selected by the production concentration evaluator; cohort ceilings never "
                "alter its observed bounds"
            ),
            "counterfactual_anchor": (
                "candidate observed_at for a near miss; this is an analysis anchor and never "
                "an activation timestamp"
            ),
            "observed_outcome_rate": "completed historical MRZ generations only; ongoing generations remain unresolved",
            "intermediate_vs_final": (
                "checkpoint pressure, displacement, tests, and sequences are intermediate behavior and never convert an ongoing episode into a final outcome"
            ),
            "signed_displacement": (
                "(observation_price - mrz_midpoint) / activation IPDA 20-week width; "
                "episode and cohort aggregation use an ordinary signed median"
            ),
            "near_midpoint": "exactly zero signed displacement; no unapproved tolerance is invented",
            "containment": "inclusive MRZ core; prices outside it are above or below core",
            "boundary_test": (
                "an upper test is at or above core upper; a lower test is at or below core lower"
            ),
            "migration_envelope": (
                "production ActiveMRZ boundaries: effective width=max(core width,instrument tick), then ±2 widths"
            ),
            "successor": (
                "incoming route plus external side, rolling latest-20 route "
                "window, four-observation minimum, and evaluate_concentration evaluator"
            ),
            "diagnosis_rubric": (
                "descriptive only: at least 8 eligible episodes; a 15 percentage-point route-supportive "
                "difference is treated as meaningfully clearer for diagnosis, never as a production threshold"
            ),
        },
        "cohorts": reports,
        "production_vs_near_miss_windows": production_vs_near_miss,
        "cross_cohort_diagnosis": cross_cohort_diagnosis(reports),
        "overall_diagnosis": overall_diagnosis(reports),
        "data_limitations": [
            "MRZ event rows omit historical activation IPDA frame, tick, and normalized span; deterministic replay supplies them.",
            "Successor direction and route are determined by the confirming external concentration, not the prior MRZ.",
            "ROUTE_CHANGED is an audit companion to MRZ_MIGRATED and is not a separate authority generation.",
            "Ongoing episodes contribute checkpoint measurements but no final outcome.",
            *reconciliation["limitations"],
        ],
        "invariants": {
            "schema_version": "4.3 unchanged",
            "payload_structure": "unchanged",
            "mrz_engine_behavior": "structure-first external successor migration",
            "operation_card_trading_window_state": "not implemented",
            "production_status": "NOT APPROVED",
        },
    }


def numeric(value: Decimal | None) -> float | None:
    return None if value is None else float(value)


def iso(value: datetime | None) -> str | None:
    return None if value is None else value.isoformat().replace("+00:00", "Z")
