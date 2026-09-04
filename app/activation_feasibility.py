from __future__ import annotations

import hashlib
import json
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Callable, Iterable, Sequence

from app.concentration import (
    ROUTE_OBSERVATION_WINDOW,
    ConcentrationEvaluation,
    ConcentrationResult,
    evaluate_concentration,
    expand_selected_seed,
)
from app.domain import Observation, Route
from app.structure import classify_structural_location


ALGORITHM_A = "A"
ALGORITHM_B = "B"
ALGORITHMS = (ALGORITHM_A, ALGORITHM_B)
MINIMUM_OBSERVATION_SETTINGS = (2, 3, 4)
ALLOWANCE_SETTINGS = tuple(Decimal(value) / Decimal("100") for value in range(1, 6))
LOW_SAMPLE_SEQUENCE_THRESHOLD = 30


@dataclass(frozen=True, slots=True)
class Scenario:
    algorithm: str
    minimum_observations: int
    allowance: Decimal

    @property
    def allowance_percent(self) -> int:
        return int(self.allowance * Decimal("100"))

    @property
    def scenario_id(self) -> str:
        return f"{self.algorithm}-{self.minimum_observations}-{self.allowance_percent}"


@dataclass(frozen=True, slots=True)
class FirstQualification:
    timestamp: datetime
    ordinal: int
    formation_duration_seconds: Decimal
    seed_observation_count: int
    expanded_observation_count: int
    proposed_lower_boundary: Decimal
    proposed_upper_boundary: Decimal
    proposed_midpoint: Decimal
    observed_span: Decimal
    ipda_high: Decimal
    ipda_low: Decimal
    ipda_width: Decimal
    allowance_price_units: Decimal
    normalized_span: Decimal
    minimum_required_allowance_pct: Decimal
    structural_location: str

    def payload(self) -> dict[str, object]:
        return {
            "first_qualifying_timestamp": iso(self.timestamp),
            "ordinal_route_observation_number": self.ordinal,
            "formation_duration_seconds": decimal_text(self.formation_duration_seconds),
            "seed_observation_count": self.seed_observation_count,
            "expanded_observation_count": self.expanded_observation_count,
            "proposed_lower_boundary": decimal_text(self.proposed_lower_boundary),
            "proposed_upper_boundary": decimal_text(self.proposed_upper_boundary),
            "proposed_midpoint": decimal_text(self.proposed_midpoint),
            "observed_span": decimal_text(self.observed_span),
            "ipda_20w_high": decimal_text(self.ipda_high),
            "ipda_20w_low": decimal_text(self.ipda_low),
            "full_ipda_width": decimal_text(self.ipda_width),
            "allowance_price_units": decimal_text(self.allowance_price_units),
            "normalized_span": decimal_text(self.normalized_span),
            "minimum_required_allowance_pct": decimal_text(
                self.minimum_required_allowance_pct
            ),
            "structural_location": self.structural_location,
        }


@dataclass(frozen=True, slots=True)
class ClosestEvaluation:
    symbol: str
    route: Route
    evaluator_identity: str
    timestamp: datetime
    newest_observation_id: str
    ordinal: int
    qualification_ratio: Decimal
    candidate_normalized_span: Decimal
    candidate_observed_span: Decimal
    candidate_lower_boundary: Decimal
    candidate_upper_boundary: Decimal
    candidate_midpoint: Decimal
    candidate_observation_count: int
    candidate_observation_ids: tuple[str, ...]
    ipda_high: Decimal
    ipda_low: Decimal
    ipda_width: Decimal
    structural_location: str | None
    structural_eligibility_passed: bool | None
    evaluation_result: str

    @property
    def minimum_required_allowance_pct(self) -> Decimal:
        return self.candidate_normalized_span * Decimal("100")

    @property
    def candidate_identity(self) -> str:
        identity = {
            "symbol": self.symbol,
            "route": self.route.value,
            "evaluator_identity": self.evaluator_identity,
            "candidate_lower": str(self.candidate_lower_boundary),
            "candidate_upper": str(self.candidate_upper_boundary),
            "candidate_midpoint": str(self.candidate_midpoint),
            "supporting_observation_ids": list(self.candidate_observation_ids),
            "newest_observation_id": self.newest_observation_id,
            "required_allowance_pct": str(self.minimum_required_allowance_pct),
            "candidate_timestamp": iso(self.timestamp),
        }
        serialized = json.dumps(
            identity,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(serialized).hexdigest()

    def payload(self, *, include_evidence_ids: bool = False) -> dict[str, object]:
        payload = {
            "timestamp": iso(self.timestamp),
            "ordinal_route_observation_number": self.ordinal,
            "qualification_ratio": decimal_text(self.qualification_ratio),
            "candidate_normalized_span": decimal_text(self.candidate_normalized_span),
            "candidate_observed_span": decimal_text(self.candidate_observed_span),
            "candidate_lower_boundary": decimal_text(self.candidate_lower_boundary),
            "candidate_upper_boundary": decimal_text(self.candidate_upper_boundary),
            "candidate_midpoint": decimal_text(self.candidate_midpoint),
            "candidate_observation_count": self.candidate_observation_count,
            "candidate_identity": self.candidate_identity,
            "evaluator_identity": self.evaluator_identity,
            "ipda_20w_high": decimal_text(self.ipda_high),
            "ipda_20w_low": decimal_text(self.ipda_low),
            "ipda_width": decimal_text(self.ipda_width),
            "minimum_required_allowance_pct": decimal_text(
                self.minimum_required_allowance_pct
            ),
            "structural_location": self.structural_location,
            "structural_eligibility_passed": self.structural_eligibility_passed,
            "evaluation_result": self.evaluation_result,
        }
        if include_evidence_ids:
            payload.update({
                "supporting_observation_ids": list(self.candidate_observation_ids),
                "candidate_event_id": self.newest_observation_id,
            })
        return payload


@dataclass(frozen=True, slots=True)
class SequenceOutcome:
    symbol: str
    route: Route
    total_observations: int
    scenario: Scenario
    eligible: bool
    classification: str
    first_qualification: FirstQualification | None
    closest_evaluation: ClosestEvaluation | None
    current_evaluation: ClosestEvaluation | None

    @property
    def activated(self) -> bool:
        return self.first_qualification is not None

    def payload(self, *, include_evidence_ids: bool = False) -> dict[str, object]:
        first = self.first_qualification.payload() if self.first_qualification else {}
        return {
            "symbol": self.symbol,
            "route": self.route.value,
            "total_stored_route_observations": self.total_observations,
            "scenario_id": self.scenario.scenario_id,
            "algorithm": self.scenario.algorithm,
            "minimum_observations": self.scenario.minimum_observations,
            "allowance_percent": self.scenario.allowance_percent,
            "eligible": self.eligible,
            "classification": self.classification,
            "activated": self.activated,
            "first_qualifying_timestamp": None,
            "ordinal_route_observation_number": None,
            "formation_duration_seconds": None,
            "seed_observation_count": None,
            "expanded_observation_count": None,
            "proposed_lower_boundary": None,
            "proposed_upper_boundary": None,
            "proposed_midpoint": None,
            "observed_span": None,
            "ipda_20w_high": None,
            "ipda_20w_low": None,
            "full_ipda_width": None,
            "allowance_price_units": None,
            "normalized_span": None,
            "minimum_required_allowance_pct": None,
            "structural_location": None,
            **first,
            "closest_qualification_ratio": (
                decimal_text(self.closest_evaluation.qualification_ratio)
                if self.closest_evaluation
                else None
            ),
            "closest_minimum_required_allowance_pct": (
                decimal_text(self.closest_evaluation.minimum_required_allowance_pct)
                if self.closest_evaluation
                else None
            ),
            "closest_evaluation": (
                self.closest_evaluation.payload(
                    include_evidence_ids=include_evidence_ids
                )
                if self.closest_evaluation
                else None
            ),
            "current_evaluation": (
                self.current_evaluation.payload(
                    include_evidence_ids=include_evidence_ids
                )
                if self.current_evaluation
                else None
            ),
        }


def iso(value: datetime | None) -> str | None:
    return None if value is None else value.isoformat().replace("+00:00", "Z")


def decimal_text(value: Decimal | None) -> str | None:
    return None if value is None else str(value)


def duration_seconds(start: datetime, end: datetime) -> Decimal:
    duration = end - start
    whole_seconds = (duration.days * 86400) + duration.seconds
    return Decimal(whole_seconds) + (Decimal(duration.microseconds) / Decimal("1000000"))


def median_decimal(values: Iterable[Decimal]) -> Decimal | None:
    ordered = sorted(values)
    if not ordered:
        return None
    midpoint = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[midpoint]
    return (ordered[midpoint - 1] + ordered[midpoint]) / Decimal("2")


def percentage(numerator: int, denominator: int) -> str | None:
    if denominator == 0:
        return None
    value = (Decimal(numerator) * Decimal("100")) / Decimal(denominator)
    return str(value.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def display_decimal(value: Decimal, places: str = "0.1") -> str:
    return str(value.quantize(Decimal(places), rounding=ROUND_HALF_UP))


def history_frequency_clause(
    summary: dict[str, object],
    *,
    singular_outcome: str,
    plural_outcome: str,
) -> str:
    frequency = summary["activation_frequency"]
    numerator = int(frequency["numerator"])
    denominator = int(frequency["denominator"])
    percent = frequency["percentage"]
    suffix = "—" if percent is None else f"{percent}%"
    history_label = "history" if denominator == 1 else "histories"
    outcome = singular_outcome if numerator == 1 else plural_outcome
    return (
        f"{numerator} of {denominator} eligible symbol-route {history_label} "
        f"{outcome} ({suffix})"
    )


def symbol_route_history_count(count: int) -> str:
    noun = "history" if count == 1 else "histories"
    return f"{count} symbol-route {noun}"


def _chronological_seed_selector(
    observations: Sequence[Observation],
    incoming_event_id: str,
    ipda_width: Decimal,
    minimum_required_count: int,
    concentration_threshold: Decimal,
):
    """Algorithm B: choose only the latest consecutive chronological seed."""
    chronological = tuple(sorted(observations, key=lambda item: item.order_key))
    selected_seed = chronological[-minimum_required_count:]
    if not selected_seed or selected_seed[-1].event_id != incoming_event_id:
        raise ValueError("chronological seed must contain the newest observation")
    return expand_selected_seed(
        chronological,
        selected_seed,
        ipda_width,
        minimum_required_count,
        concentration_threshold,
        tested_window_count=1,
    )


def evaluate_feasibility_concentration(
    observations: Sequence[Observation],
    route: Route,
    scenario: Scenario,
) -> ConcentrationEvaluation:
    if scenario.algorithm not in ALGORITHMS:
        raise ValueError(f"unsupported feasibility algorithm: {scenario.algorithm}")
    return evaluate_concentration(
        observations,
        route,
        minimum_required_count=scenario.minimum_observations,
        concentration_threshold=scenario.allowance,
        seed_selector=(
            None if scenario.algorithm == ALGORITHM_A else _chronological_seed_selector
        ),
    )


def production_near_misses(
    sequence_details: Sequence[dict[str, object]],
    evaluation_key: str,
    *,
    scope: str,
    preliminary: bool,
    active_symbols: set[str] | None = None,
    limit: int = 5,
) -> list[dict[str, object]]:
    """Return the exact actionable near-miss cards used by the operator UI."""
    production_id = Scenario(ALGORITHM_A, 4, Decimal("0.01")).scenario_id
    configured_allowance = Decimal("1")
    active = active_symbols or set()
    near_misses: list[dict[str, object]] = []
    for row in sequence_details:
        evaluation = row[evaluation_key]
        if (
            row["scenario_id"] != production_id
            or not row["eligible"]
            or row["activated"]
            or row["symbol"] in active
            or evaluation is None
            or evaluation["structural_eligibility_passed"] is not True
        ):
            continue
        required = Decimal(evaluation["minimum_required_allowance_pct"])
        if required <= configured_allowance or required > Decimal("2"):
            continue
        shortfall = required - configured_allowance
        scope_label = (
            "Current minimum allowance required"
            if scope == "CURRENT"
            else "Closest historical minimum allowance required"
        )
        near_miss = {
            "code": f"PRODUCTION_SPATIAL_NEAR_MISS_{scope}",
            "heading": f"{row['symbol']} · {row['route']}",
            "text": (
                f"{scope_label} · {display_decimal(required, '0.01')}%. "
                "Current allowance · 1.00%. Shortfall · "
                f"{display_decimal(shortfall, '0.01')} percentage points."
            ),
            "measurement_scope": scope,
            "numerator": evaluation["candidate_observation_count"],
            "denominator": row["total_stored_route_observations"],
            "scenario_ids": [production_id],
            "small_sample": preliminary,
            "symbol": row["symbol"],
            "route": row["route"],
            "minimum_required_allowance_pct": decimal_text(required),
            "configured_allowance_pct": decimal_text(configured_allowance),
            "shortfall_percentage_points": decimal_text(shortfall),
            "candidate_lower_boundary": evaluation["candidate_lower_boundary"],
            "candidate_upper_boundary": evaluation["candidate_upper_boundary"],
            "candidate_midpoint": evaluation["candidate_midpoint"],
            "candidate_observation_count": evaluation[
                "candidate_observation_count"
            ],
            "candidate_identity": evaluation["candidate_identity"],
            "evaluator_identity": evaluation["evaluator_identity"],
            "structural_location": evaluation["structural_location"],
            "ipda_20w_high": evaluation["ipda_20w_high"],
            "ipda_20w_low": evaluation["ipda_20w_low"],
            "ipda_width": evaluation["ipda_width"],
            "total_stored_route_observations": row[
                "total_stored_route_observations"
            ],
            "candidate_timestamp": evaluation["timestamp"],
        }
        if "supporting_observation_ids" in evaluation:
            near_miss.update({
                "supporting_observation_ids": evaluation[
                    "supporting_observation_ids"
                ],
                "candidate_event_id": evaluation["candidate_event_id"],
            })
        near_misses.append(near_miss)
    near_misses.sort(
        key=lambda item: (
            Decimal(item["minimum_required_allowance_pct"]),
            item["symbol"],
            item["route"],
        )
    )
    return near_misses[:limit]


def current_production_near_misses(
    observations: Sequence[Observation],
    *,
    active_symbols: set[str] | None = None,
    limit: int = 5,
) -> list[dict[str, object]]:
    """Evaluate only the canonical production scenario for command/episode use."""
    grouped: dict[tuple[str, Route], list[Observation]] = defaultdict(list)
    for observation in observations:
        grouped[(observation.symbol, observation.route)].append(observation)
    scenario = Scenario(ALGORITHM_A, 4, Decimal("0.01"))
    rows = [
        ActivationFeasibilityService.evaluate_sequence(
            tuple(sorted(group, key=lambda item: item.order_key)),
            scenario,
        ).payload(include_evidence_ids=True)
        for _key, group in sorted(
            grouped.items(),
            key=lambda item: (item[0][0], item[0][1].value),
        )
    ]
    return production_near_misses(
        rows,
        "current_evaluation",
        scope="CURRENT",
        preliminary=len(grouped) < LOW_SAMPLE_SEQUENCE_THRESHOLD,
        active_symbols=active_symbols,
        limit=limit,
    )


class ActivationFeasibilityService:
    """Read-only chronological replay of hypothetical initial activations."""

    def __init__(
        self,
        observation_reader: Callable[[], Sequence[Observation]],
        *,
        active_symbol_reader: Callable[[], Sequence[str]] | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._observation_reader = observation_reader
        self._active_symbol_reader = active_symbol_reader or (lambda: ())
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def generate_report(self) -> dict[str, object]:
        observations = tuple(self._observation_reader())
        grouped: dict[tuple[str, Route], list[Observation]] = defaultdict(list)
        for observation in observations:
            grouped[(observation.symbol, observation.route)].append(observation)
        ordered_groups = {
            key: tuple(sorted(rows, key=lambda item: item.order_key))
            for key, rows in sorted(
                grouped.items(),
                key=lambda item: (item[0][0], item[0][1].value),
            )
        }

        scenarios = tuple(
            Scenario(algorithm, minimum, allowance)
            for algorithm in ALGORITHMS
            for minimum in MINIMUM_OBSERVATION_SETTINGS
            for allowance in ALLOWANCE_SETTINGS
        )
        outcomes = tuple(
            self.evaluate_sequence(rows, scenario)
            for scenario in scenarios
            for rows in ordered_groups.values()
        )
        outcomes_by_scenario: dict[str, list[SequenceOutcome]] = defaultdict(list)
        for outcome in outcomes:
            outcomes_by_scenario[outcome.scenario.scenario_id].append(outcome)

        scenario_summaries = [
            self._scenario_summary(scenario, outcomes_by_scenario[scenario.scenario_id])
            for scenario in scenarios
        ]
        comparisons = [
            self._comparison(
                minimum,
                allowance,
                outcomes_by_scenario[
                    Scenario(ALGORITHM_A, minimum, allowance).scenario_id
                ],
                outcomes_by_scenario[
                    Scenario(ALGORITHM_B, minimum, allowance).scenario_id
                ],
            )
            for minimum in MINIMUM_OBSERVATION_SETTINGS
            for allowance in ALLOWANCE_SETTINGS
        ]

        observed_times = [item.observed_at for item in observations]
        production_id = Scenario(ALGORITHM_A, 4, Decimal("0.01")).scenario_id
        production_summary = next(
            summary for summary in scenario_summaries if summary["scenario_id"] == production_id
        )
        production_activations = []
        for outcome in outcomes_by_scenario[production_id]:
            first = outcome.first_qualification
            if first is None:
                continue
            production_activations.append({
                "symbol": outcome.symbol,
                "route": outcome.route.value,
                "core_mrz_lower": decimal_text(first.proposed_lower_boundary),
                "core_mrz_upper": decimal_text(first.proposed_upper_boundary),
                "activated_at": iso(first.timestamp),
                "minimum_observations": outcome.scenario.minimum_observations,
                "allowance_percent": outcome.scenario.allowance_percent,
            })
        production_activations.sort(key=lambda item: (item["symbol"], item["route"]))
        report = {
            "generated_at": iso(self._clock()),
            "earliest_observation_at": iso(min(observed_times)) if observed_times else None,
            "latest_observation_at": iso(max(observed_times)) if observed_times else None,
            "total_observations_evaluated": len(observations),
            "total_normalized_symbols": len({item.symbol for item in observations}),
            "total_symbol_route_sequences": len(ordered_groups),
            "algorithm_descriptions": {
                ALGORITHM_A: (
                    "Tightest newest-participating contiguous price-space seed from the "
                    "latest 20 route observations, followed by production expansion."
                ),
                ALGORITHM_B: (
                    "Latest consecutive chronological seed from the latest 20 route "
                    "observations, followed by the same production expansion."
                ),
            },
            "current_production_rule": {
                "scenario_id": production_id,
                "algorithm": ALGORITHM_A,
                "minimum_observations": 4,
                "allowance_percent": 1,
                "label": "Algorithm A · 4 observations · 1.00%",
                "result": production_summary,
                "activations": production_activations,
            },
            "small_sample_sequence_threshold": LOW_SAMPLE_SEQUENCE_THRESHOLD,
            "has_small_sample_scenarios": any(
                bool(summary["small_sample"]) for summary in scenario_summaries
            ),
            "scenarios": scenario_summaries,
            "comparisons": comparisons,
            "sequence_details": [outcome.payload() for outcome in outcomes],
        }
        report["diagnosis"] = self._diagnosis(
            report,
            active_symbols=set(self._active_symbol_reader()),
        )
        return report

    @staticmethod
    def evaluate_sequence(
        observations: Sequence[Observation],
        scenario: Scenario,
    ) -> SequenceOutcome:
        symbol = observations[0].symbol
        route = observations[0].route
        eligible = len(observations) >= scenario.minimum_observations
        if not eligible:
            return SequenceOutcome(
                symbol=symbol,
                route=route,
                total_observations=len(observations),
                scenario=scenario,
                eligible=False,
                classification="INSUFFICIENT",
                first_qualification=None,
                closest_evaluation=None,
                current_evaluation=None,
            )

        window: deque[Observation] = deque(maxlen=ROUTE_OBSERVATION_WINDOW)
        first_qualification: FirstQualification | None = None
        closest: ClosestEvaluation | None = None
        current: ClosestEvaluation | None = None
        for ordinal, incoming in enumerate(observations, 1):
            window.append(incoming)
            if len(window) < scenario.minimum_observations:
                continue
            evaluation = evaluate_feasibility_concentration(tuple(window), route, scenario)
            diagnostic = evaluation.diagnostic
            current = None
            if diagnostic.normalized_span is not None and diagnostic.observed_span is not None:
                if diagnostic.selected_lower is None or diagnostic.selected_upper is None:
                    raise RuntimeError("measurable candidate must include its price range")
                candidate = ClosestEvaluation(
                    symbol=symbol,
                    route=route,
                    evaluator_identity=f"{scenario.scenario_id}:production-concentration-v1",
                    timestamp=incoming.observed_at,
                    newest_observation_id=incoming.event_id,
                    ordinal=ordinal,
                    qualification_ratio=diagnostic.normalized_span / scenario.allowance,
                    candidate_normalized_span=diagnostic.normalized_span,
                    candidate_observed_span=diagnostic.observed_span,
                    candidate_lower_boundary=diagnostic.selected_lower,
                    candidate_upper_boundary=diagnostic.selected_upper,
                    candidate_midpoint=(
                        diagnostic.selected_lower + diagnostic.selected_upper
                    ) / Decimal("2"),
                    candidate_observation_count=diagnostic.selected_observation_count,
                    candidate_observation_ids=diagnostic.selected_observation_ids,
                    ipda_high=incoming.ipda_20w_high,
                    ipda_low=incoming.ipda_20w_low,
                    ipda_width=incoming.ipda_width,
                    structural_location=(
                        location.value
                        if (
                            location := classify_structural_location(
                                route,
                                diagnostic.proposed_midpoint,
                                incoming.ipda_20w_high,
                                incoming.ipda_20w_low,
                            )
                        )
                        else None
                    ),
                    structural_eligibility_passed=(
                        diagnostic.structural_eligibility_passed
                    ),
                    evaluation_result=diagnostic.result.value,
                )
                current = candidate
                if closest is None or candidate.qualification_ratio < closest.qualification_ratio:
                    closest = candidate

            if evaluation.result is not ConcentrationResult.QUALIFIES:
                continue
            if first_qualification is not None:
                continue
            if evaluation.cluster is None:
                raise RuntimeError("qualifying evaluation must include an expanded cluster")
            minimum_required_allowance_pct = diagnostic.minimum_required_allowance_pct
            if minimum_required_allowance_pct is None:
                raise RuntimeError("qualifying evaluation must include a measurable seed")
            seed_ids = set(diagnostic.selected_observation_ids)
            seed_observations = tuple(item for item in window if item.event_id in seed_ids)
            if len(seed_observations) != scenario.minimum_observations:
                raise RuntimeError("qualifying seed observations could not be reconstructed")
            cluster = evaluation.cluster
            first_qualification = FirstQualification(
                timestamp=incoming.observed_at,
                ordinal=ordinal,
                formation_duration_seconds=duration_seconds(
                    min(item.observed_at for item in seed_observations),
                    incoming.observed_at,
                ),
                seed_observation_count=len(seed_observations),
                expanded_observation_count=len(cluster.members),
                proposed_lower_boundary=cluster.lower,
                proposed_upper_boundary=cluster.upper,
                proposed_midpoint=cluster.midpoint,
                observed_span=cluster.upper - cluster.lower,
                ipda_high=incoming.ipda_20w_high,
                ipda_low=incoming.ipda_20w_low,
                ipda_width=incoming.ipda_width,
                allowance_price_units=scenario.allowance * incoming.ipda_width,
                normalized_span=cluster.normalized_span,
                minimum_required_allowance_pct=minimum_required_allowance_pct,
                structural_location=(
                    diagnostic.proposed_structural_location.value
                    if diagnostic.proposed_structural_location
                    else "unclassified"
                ),
            )

        if first_qualification is not None:
            classification = "QUALIFIED"
        elif closest is not None and closest.qualification_ratio <= Decimal("2"):
            classification = "NEAR_MISS"
        else:
            classification = "DISPERSED"
        return SequenceOutcome(
            symbol=symbol,
            route=route,
            total_observations=len(observations),
            scenario=scenario,
            eligible=True,
            classification=classification,
            first_qualification=first_qualification,
            closest_evaluation=closest,
            current_evaluation=current,
        )

    @staticmethod
    def _scenario_summary(
        scenario: Scenario,
        outcomes: Sequence[SequenceOutcome],
    ) -> dict[str, object]:
        eligible = [item for item in outcomes if item.eligible]
        activated = [item for item in eligible if item.activated]
        firsts = [item.first_qualification for item in activated]
        ordinal_median = median_decimal(
            Decimal(item.ordinal) for item in firsts if item is not None
        )
        duration_median = median_decimal(
            item.formation_duration_seconds for item in firsts if item is not None
        )
        normalized_span_median = median_decimal(
            item.normalized_span for item in firsts if item is not None
        )
        minimum_required_allowance_pct_median = median_decimal(
            item.minimum_required_allowance_pct for item in firsts if item is not None
        )
        return {
            "scenario_id": scenario.scenario_id,
            "algorithm": scenario.algorithm,
            "minimum_observations": scenario.minimum_observations,
            "allowance_percent": scenario.allowance_percent,
            "eligible_symbol_route_sequences": len(eligible),
            "hypothetical_activations": len(activated),
            "activation_frequency": {
                "numerator": len(activated),
                "denominator": len(eligible),
                "percentage": percentage(len(activated), len(eligible)),
            },
            "qualified_sequences": len(activated),
            "near_miss_sequences": sum(
                item.classification == "NEAR_MISS" for item in eligible
            ),
            "dispersed_sequences": sum(
                item.classification == "DISPERSED" for item in eligible
            ),
            "insufficient_sequences": sum(not item.eligible for item in outcomes),
            "median_ordinal_observation_at_qualification": decimal_text(ordinal_median),
            "median_formation_duration_seconds": decimal_text(duration_median),
            "median_normalized_span_at_qualification": decimal_text(
                normalized_span_median
            ),
            "median_minimum_required_allowance_pct_at_qualification": decimal_text(
                minimum_required_allowance_pct_median
            ),
            "small_sample": len(eligible) < LOW_SAMPLE_SEQUENCE_THRESHOLD,
            "is_current_production_rule": (
                scenario.algorithm == ALGORITHM_A
                and scenario.minimum_observations == 4
                and scenario.allowance == Decimal("0.01")
            ),
        }

    @staticmethod
    def _comparison(
        minimum: int,
        allowance: Decimal,
        algorithm_a: Sequence[SequenceOutcome],
        algorithm_b: Sequence[SequenceOutcome],
    ) -> dict[str, object]:
        a_by_key = {(item.symbol, item.route): item for item in algorithm_a}
        b_by_key = {(item.symbol, item.route): item for item in algorithm_b}
        keys = sorted(a_by_key, key=lambda key: (key[0], key[1].value))
        eligible_keys = [key for key in keys if a_by_key[key].eligible]
        a_activated = {key for key in eligible_keys if a_by_key[key].activated}
        b_activated = {key for key in eligible_keys if b_by_key[key].activated}
        both = a_activated & b_activated
        a_only = a_activated - b_activated
        b_only = b_activated - a_activated
        neither = set(eligible_keys) - (a_activated | b_activated)

        timestamp_differences = []
        ordinal_differences = []
        span_differences = []
        for key in both:
            a_first = a_by_key[key].first_qualification
            b_first = b_by_key[key].first_qualification
            if a_first is None or b_first is None:
                raise RuntimeError("activated comparison must include first qualification")
            timestamp_differences.append(
                duration_seconds(a_first.timestamp, b_first.timestamp)
            )
            ordinal_differences.append(Decimal(b_first.ordinal - a_first.ordinal))
            span_differences.append(b_first.observed_span - a_first.observed_span)

        a_ratios = [
            item.closest_evaluation.qualification_ratio
            for item in algorithm_a
            if item.eligible and item.closest_evaluation is not None
        ]
        b_ratios = [
            item.closest_evaluation.qualification_ratio
            for item in algorithm_b
            if item.eligible and item.closest_evaluation is not None
        ]
        a_required_allowances = [
            item.closest_evaluation.minimum_required_allowance_pct
            for item in algorithm_a
            if item.eligible and item.closest_evaluation is not None
        ]
        b_required_allowances = [
            item.closest_evaluation.minimum_required_allowance_pct
            for item in algorithm_b
            if item.eligible and item.closest_evaluation is not None
        ]
        a_percentage = percentage(len(a_activated), len(eligible_keys))
        b_percentage = percentage(len(b_activated), len(eligible_keys))
        difference = (
            Decimal(b_percentage) - Decimal(a_percentage)
            if a_percentage is not None and b_percentage is not None
            else None
        )
        disagreements = []
        for key in sorted(a_only | b_only, key=lambda item: (item[0], item[1].value)):
            a_outcome = a_by_key[key]
            b_outcome = b_by_key[key]
            disagreements.append(
                {
                    "symbol": key[0],
                    "route": key[1].value,
                    "category": "A_ONLY" if key in a_only else "B_ONLY",
                    "algorithm_a": {
                        "activated": a_outcome.activated,
                        "classification": a_outcome.classification,
                        "first_qualifying_timestamp": (
                            iso(a_outcome.first_qualification.timestamp)
                            if a_outcome.first_qualification
                            else None
                        ),
                        "closest_qualification_ratio": (
                            decimal_text(a_outcome.closest_evaluation.qualification_ratio)
                            if a_outcome.closest_evaluation
                            else None
                        ),
                        "closest_minimum_required_allowance_pct": (
                            decimal_text(
                                a_outcome.closest_evaluation.minimum_required_allowance_pct
                            )
                            if a_outcome.closest_evaluation
                            else None
                        ),
                    },
                    "algorithm_b": {
                        "activated": b_outcome.activated,
                        "classification": b_outcome.classification,
                        "first_qualifying_timestamp": (
                            iso(b_outcome.first_qualification.timestamp)
                            if b_outcome.first_qualification
                            else None
                        ),
                        "closest_qualification_ratio": (
                            decimal_text(b_outcome.closest_evaluation.qualification_ratio)
                            if b_outcome.closest_evaluation
                            else None
                        ),
                        "closest_minimum_required_allowance_pct": (
                            decimal_text(
                                b_outcome.closest_evaluation.minimum_required_allowance_pct
                            )
                            if b_outcome.closest_evaluation
                            else None
                        ),
                    },
                }
            )

        return {
            "comparison_id": f"AB-{minimum}-{int(allowance * Decimal('100'))}",
            "minimum_observations": minimum,
            "allowance_percent": int(allowance * Decimal("100")),
            "eligible_symbol_route_sequences": len(eligible_keys),
            "algorithm_a_activations": len(a_activated),
            "algorithm_b_activations": len(b_activated),
            "algorithm_a_frequency": {
                "numerator": len(a_activated),
                "denominator": len(eligible_keys),
                "percentage": a_percentage,
            },
            "algorithm_b_frequency": {
                "numerator": len(b_activated),
                "denominator": len(eligible_keys),
                "percentage": b_percentage,
            },
            "activation_frequency_difference_percentage_points_b_minus_a": decimal_text(
                difference
            ),
            "both_activated": len(both),
            "algorithm_a_only": len(a_only),
            "algorithm_b_only": len(b_only),
            "neither_activated": len(neither),
            "median_activation_timestamp_difference_seconds_b_minus_a": decimal_text(
                median_decimal(timestamp_differences)
            ),
            "median_ordinal_observation_difference_b_minus_a": decimal_text(
                median_decimal(ordinal_differences)
            ),
            "median_proposed_span_difference_b_minus_a": decimal_text(
                median_decimal(span_differences)
            ),
            "median_algorithm_a_qualification_ratio": decimal_text(
                median_decimal(a_ratios)
            ),
            "median_algorithm_b_qualification_ratio": decimal_text(
                median_decimal(b_ratios)
            ),
            "median_algorithm_a_minimum_required_allowance_pct": decimal_text(
                median_decimal(a_required_allowances)
            ),
            "median_algorithm_b_minimum_required_allowance_pct": decimal_text(
                median_decimal(b_required_allowances)
            ),
            "disagreements": disagreements,
            "small_sample": len(eligible_keys) < LOW_SAMPLE_SEQUENCE_THRESHOLD,
        }

    @staticmethod
    def _diagnosis(
        report: dict[str, object],
        *,
        active_symbols: set[str] | None = None,
    ) -> dict[str, object]:
        """Generate fixed, auditable commentary from the completed report payload."""
        scenarios = {
            item["scenario_id"]: item for item in report["scenarios"]
        }
        production_id = report["current_production_rule"]["scenario_id"]
        production = scenarios[production_id]
        production_eligible = int(production["eligible_symbol_route_sequences"])
        production_activated = int(production["hypothetical_activations"])
        preliminary = production_eligible < LOW_SAMPLE_SEQUENCE_THRESHOLD

        if preliminary:
            sample = {
                "code": "SAMPLE_PRELIMINARY",
                "heading": "Sample confidence · Preliminary",
                "text": (
                    f"Only {symbol_route_history_count(production_eligible)} contain at least "
                    "four observations. The sample is insufficient for a production-policy "
                    "conclusion."
                ),
                "numerator": production_eligible,
                "denominator": LOW_SAMPLE_SEQUENCE_THRESHOLD,
                "scenario_ids": [production_id],
                "small_sample": True,
            }
        else:
            sample = {
                "code": "SAMPLE_OBSERVED_HISTORY",
                "heading": "Sample assessment · Observed history",
                "text": (
                    f"{symbol_route_history_count(production_eligible)} contain at least four "
                    "observations. Frequencies remain observed historical frequencies, not "
                    "predictive probabilities."
                ),
                "numerator": production_eligible,
                "denominator": LOW_SAMPLE_SEQUENCE_THRESHOLD,
                "scenario_ids": [production_id],
                "small_sample": False,
            }

        if production_eligible == 0:
            production_code = "PRODUCTION_INSUFFICIENT_OBSERVATIONS"
            production_heading = "Production feasibility · Insufficient observations"
            production_text = "No symbol-route history currently contains four observations."
        elif production_activated == 0:
            production_code = "PRODUCTION_NO_ACTIVATION_OBSERVED"
            production_heading = "Production feasibility · No MRZ formed"
            production_text = (
                "The current production rule formed no MRZ in "
                f"{production_eligible} eligible symbol-route "
                f"{'history' if production_eligible == 1 else 'histories'}."
            )
        else:
            production_code = "PRODUCTION_ACTIVATION_OBSERVED"
            production_heading = "Production feasibility · MRZ formation observed"
            production_text = (
                "The current production rule formed an MRZ in "
                f"{production_activated} of {production_eligible} eligible symbol-route "
                f"{'history' if production_eligible == 1 else 'histories'} "
                f"({production['activation_frequency']['percentage']}%)."
            )
        production_feasibility = {
            "code": production_code,
            "heading": production_heading,
            "text": production_text,
            "numerator": production_activated,
            "denominator": production_eligible,
            "scenario_ids": [production_id],
            "small_sample": preliminary,
        }

        count_rows = [scenarios[f"A-{minimum}-1"] for minimum in (2, 3, 4)]
        count_settings = [
            {
                "scenario_id": row["scenario_id"],
                "minimum_observations": row["minimum_observations"],
                "numerator": row["activation_frequency"]["numerator"],
                "denominator": row["activation_frequency"]["denominator"],
                "percentage": row["activation_frequency"]["percentage"],
            }
            for row in count_rows
        ]
        count_text = "At the 1.00% allowance, Algorithm A produced: " + "; ".join(
            f"{row['minimum_observations']}-observation requirement · "
            f"{history_frequency_clause(row, singular_outcome='qualifies', plural_outcome='qualify')}"
            for row in count_rows
        ) + "."
        count_percentages = {
            row["activation_frequency"]["percentage"] for row in count_rows
        }
        if len(count_percentages) > 1:
            count_text += (
                " Qualification frequency changed across the available count settings. "
                "Denominators differ because not every symbol-route history contains enough "
                "observations for each requirement."
            )
        else:
            count_text += (
                " Qualification frequency was the same across the available count settings. "
                "Denominators may differ because not every symbol-route history contains "
                "enough observations for each requirement."
            )
        count_sensitivity = {
            "code": "COUNT_SENSITIVITY_OBSERVED",
            "heading": "Count sensitivity",
            "text": count_text,
            "numerator": production_activated,
            "denominator": production_eligible,
            "scenario_ids": [row["scenario_id"] for row in count_rows],
            "small_sample": any(bool(row["small_sample"]) for row in count_rows),
            "settings": count_settings,
        }

        allowance_rows = [scenarios[f"A-4-{allowance}"] for allowance in range(1, 6)]
        first_activating = next(
            (
                int(row["allowance_percent"])
                for row in allowance_rows
                if int(row["hypothetical_activations"]) > 0
            ),
            None,
        )
        increases = []
        for previous, current in zip(allowance_rows, allowance_rows[1:]):
            previous_count = int(previous["hypothetical_activations"])
            current_count = int(current["hypothetical_activations"])
            if current_count > previous_count:
                increases.append({
                    "from_allowance_pct": previous["allowance_percent"],
                    "to_allowance_pct": current["allowance_percent"],
                    "from_activations": previous_count,
                    "to_activations": current_count,
                    "scenario_ids": [previous["scenario_id"], current["scenario_id"]],
                })

        plateaus = []
        plateau_start = 0
        while plateau_start < len(allowance_rows):
            plateau_end = plateau_start
            activation_count = int(
                allowance_rows[plateau_start]["hypothetical_activations"]
            )
            while (
                plateau_end + 1 < len(allowance_rows)
                and int(allowance_rows[plateau_end + 1]["hypothetical_activations"])
                == activation_count
            ):
                plateau_end += 1
            if plateau_end > plateau_start:
                plateaus.append({
                    "from_allowance_pct": allowance_rows[plateau_start]["allowance_percent"],
                    "to_allowance_pct": allowance_rows[plateau_end]["allowance_percent"],
                    "activation_count": activation_count,
                    "scenario_ids": [
                        row["scenario_id"]
                        for row in allowance_rows[plateau_start : plateau_end + 1]
                    ],
                })
            plateau_start = plateau_end + 1

        allowance_text = (
            "With a four-observation requirement, Algorithm A produced: "
            + "; ".join(
                f"{Decimal(row['allowance_percent']):.2f}% allowance · "
                f"{history_frequency_clause(row, singular_outcome='forms an MRZ', plural_outcome='form an MRZ')}"
                for row in allowance_rows
            )
            + "."
        )
        if first_activating is None:
            allowance_text += " No tested allowance formed an MRZ."
        else:
            allowance_text += (
                f" The first tested allowance that formed an MRZ was {first_activating:.2f}%."
            )
        for increase in increases:
            allowance_text += (
                f" Increasing from {increase['from_allowance_pct']}% to "
                f"{increase['to_allowance_pct']}% increased MRZ formations from "
                f"{increase['from_activations']} to {increase['to_activations']}."
            )
        for plateau in plateaus:
            allowance_text += (
                f" Increasing from {plateau['from_allowance_pct']}% through "
                f"{plateau['to_allowance_pct']}% produced no additional MRZ formations "
                f"({plateau['activation_count']} throughout)."
            )
        allowance_sensitivity = {
            "code": "ALLOWANCE_SENSITIVITY_OBSERVED",
            "heading": "Allowance sensitivity",
            "text": allowance_text,
            "numerator": production_activated,
            "denominator": production_eligible,
            "scenario_ids": [row["scenario_id"] for row in allowance_rows],
            "small_sample": any(bool(row["small_sample"]) for row in allowance_rows),
            "first_activating_allowance_pct": first_activating,
            "increases": increases,
            "plateaus": plateaus,
            "settings": [
                {
                    "scenario_id": row["scenario_id"],
                    "allowance_pct": row["allowance_percent"],
                    "numerator": row["activation_frequency"]["numerator"],
                    "denominator": row["activation_frequency"]["denominator"],
                    "percentage": row["activation_frequency"]["percentage"],
                }
                for row in allowance_rows
            ],
        }

        comparisons = report["comparisons"]
        equal_counts = sum(
            int(row["algorithm_a_activations"]) == int(row["algorithm_b_activations"])
            for row in comparisons
        )
        a_more = sum(
            int(row["algorithm_a_activations"]) > int(row["algorithm_b_activations"])
            for row in comparisons
        )
        b_more = sum(
            int(row["algorithm_b_activations"]) > int(row["algorithm_a_activations"])
            for row in comparisons
        )
        largest = None
        for row in comparisons:
            denominator = int(row["eligible_symbol_route_sequences"])
            if denominator == 0:
                continue
            signed_difference = (
                Decimal(int(row["algorithm_b_activations"]) - int(row["algorithm_a_activations"]))
                * Decimal("100")
                / Decimal(denominator)
            )
            candidate = (abs(signed_difference), signed_difference, row)
            if largest is None or candidate[0] > largest[0]:
                largest = candidate
        comparison_text = (
            f"The algorithms produced equal MRZ formation counts in {equal_counts} of "
            f"{len(comparisons)} scenarios. Algorithm A formed more MRZs in "
            f"{a_more} scenarios. Algorithm B formed more MRZs in {b_more} scenarios."
        )
        if largest is not None:
            absolute_difference, signed_difference, largest_row = largest
            direction = (
                "Algorithm B above Algorithm A"
                if signed_difference > 0
                else "Algorithm A above Algorithm B"
                if signed_difference < 0
                else "no difference"
            )
            comparison_text += (
                " The largest observed frequency difference was "
                f"{display_decimal(absolute_difference)} percentage points in "
                f"{largest_row['comparison_id']} ({direction})."
            )
            largest_payload = {
                "comparison_id": largest_row["comparison_id"],
                "difference_percentage_points": decimal_text(absolute_difference),
                "signed_b_minus_a_percentage_points": decimal_text(signed_difference),
            }
        else:
            largest_payload = None
        algorithm_comparison = {
            "code": "ALGORITHM_COUNTS_COMPARED",
            "heading": "Algorithm comparison",
            "text": comparison_text,
            "numerator": equal_counts,
            "denominator": len(comparisons),
            "scenario_ids": [row["comparison_id"] for row in comparisons],
            "small_sample": any(bool(row["small_sample"]) for row in comparisons),
            "equal_activation_counts": equal_counts,
            "algorithm_a_more": a_more,
            "algorithm_b_more": b_more,
            "largest_frequency_difference": largest_payload,
        }

        production_allowance = int(production["allowance_percent"])
        candidate_row = next(
            (
                row
                for row in allowance_rows
                if int(row["allowance_percent"]) > production_allowance
                and int(row["hypothetical_activations"]) > production_activated
            ),
            None,
        )
        candidate_policy_evaluation: dict[str, object]
        if candidate_row is None:
            candidate_policy_evaluation = {
                "code": "POLICY_CANDIDATE_NOT_OBSERVED",
                "heading": "Candidate Policy Evaluation",
                "status": "NO_CANDIDATE_IDENTIFIED",
                "text": (
                    "No tested allowance increase formed more MRZs than the current "
                    "production rule in this sample."
                ),
                "candidate": None,
                "current": {
                    "scenario_id": production_id,
                    "algorithm": production["algorithm"],
                    "minimum_observations": production["minimum_observations"],
                    "allowance_percent": production["allowance_percent"],
                    "activation_frequency": production["activation_frequency"],
                },
                "selection_basis": [
                    "No tested higher allowance improved MRZ formation coverage.",
                    "Production parameters remain unchanged.",
                    (
                        "Sample remains preliminary."
                        if preliminary
                        else "Results remain descriptive historical evidence."
                    ),
                ],
                "scenario_ids": [row["scenario_id"] for row in allowance_rows],
                "small_sample": preliminary,
            }
        else:
            candidate_allowance = int(candidate_row["allowance_percent"])
            candidate_activations = int(candidate_row["hypothetical_activations"])
            wider_rows = [
                row
                for row in allowance_rows
                if int(row["allowance_percent"]) > candidate_allowance
            ]
            selection_basis = [
                (
                    "Maintains the current "
                    f"{production['minimum_observations']}-observation evidence requirement."
                ),
                (
                    "First tested allowance increase with a material improvement in MRZ "
                    "formation coverage."
                ),
            ]
            if wider_rows and all(
                int(row["hypothetical_activations"]) == candidate_activations
                for row in wider_rows
            ):
                selection_basis.append(
                    "Wider tested allowances from "
                    f"{Decimal(wider_rows[0]['allowance_percent']):.2f}%–"
                    f"{Decimal(wider_rows[-1]['allowance_percent']):.2f}% produced no "
                    "additional MRZ formations in the current sample."
                )
            selection_basis.append(
                "Sample remains preliminary."
                if preliminary
                else "Results remain descriptive historical evidence."
            )
            candidate_policy_evaluation = {
                "code": "POLICY_CANDIDATE_UNDER_EVALUATION",
                "heading": "Candidate Policy Evaluation",
                "status": "CANDIDATE_IDENTIFIED",
                "text": (
                    "This parameter combination is the first tested allowance increase "
                    "that improved MRZ formation coverage while retaining the production "
                    "observation requirement. It is an evidence-monitoring candidate only."
                ),
                "candidate": {
                    "scenario_id": candidate_row["scenario_id"],
                    "algorithm": candidate_row["algorithm"],
                    "minimum_observations": candidate_row["minimum_observations"],
                    "allowance_percent": candidate_row["allowance_percent"],
                    "activation_frequency": candidate_row["activation_frequency"],
                },
                "current": {
                    "scenario_id": production_id,
                    "algorithm": production["algorithm"],
                    "minimum_observations": production["minimum_observations"],
                    "allowance_percent": production["allowance_percent"],
                    "activation_frequency": production["activation_frequency"],
                },
                "selection_basis": selection_basis,
                "scenario_ids": [production_id, candidate_row["scenario_id"]],
                "small_sample": preliminary,
            }

        current_near_misses = production_near_misses(
            report["sequence_details"],
            "current_evaluation",
            scope="CURRENT",
            preliminary=preliminary,
            active_symbols=active_symbols,
        )
        historical_near_misses = production_near_misses(
            report["sequence_details"],
            "closest_evaluation",
            scope="HISTORICAL_CLOSEST",
            preliminary=preliminary,
            active_symbols=set(),
        )
        current_by_history = {
            (item["symbol"], item["route"]): item for item in current_near_misses
        }
        for historical in historical_near_misses:
            current = current_by_history.get((historical["symbol"], historical["route"]))
            historical["matches_current_candidate"] = bool(
                current
                and all(
                    current[field] == historical[field]
                    for field in (
                        "minimum_required_allowance_pct",
                        "candidate_lower_boundary",
                        "candidate_upper_boundary",
                        "candidate_observation_count",
                        "candidate_timestamp",
                    )
                )
            )

        interpretation_parts = []
        production_rule_text = (
            f"The current production rule ({production['minimum_observations']} observations "
            f"+ {Decimal(production['allowance_percent']):.2f}% allowance)"
        )
        if production_eligible == 0:
            interpretation_parts.append(
                f"{production_rule_text} has no eligible symbol-route history in the "
                "current sample."
            )
        elif production_activated == 0:
            interpretation_parts.append(
                f"{production_rule_text} formed no MRZ in {production_eligible} "
                f"eligible symbol-route {'history' if production_eligible == 1 else 'histories'}."
            )
        else:
            interpretation_parts.append(
                f"{production_rule_text} formed an MRZ in {production_activated} of "
                f"{production_eligible} eligible symbol-route "
                f"{'history' if production_eligible == 1 else 'histories'}."
            )

        interpretation_parts.append(
            f"At {Decimal(production['allowance_percent']):.2f}% allowance, observed "
            "MRZ formations by minimum count were: "
            + "; ".join(
                f"{row['minimum_observations']} observations · "
                f"{row['activation_frequency']['numerator']} of "
                f"{row['activation_frequency']['denominator']}"
                for row in count_rows
            )
            + "."
        )

        candidate = candidate_policy_evaluation["candidate"]
        if candidate is not None:
            wider_rows = [
                row
                for row in allowance_rows
                if int(row["allowance_percent"]) > int(candidate["allowance_percent"])
            ]
            candidate_activations = int(
                candidate["activation_frequency"]["numerator"]
            )
            candidate_statement = (
                "The current sample shows that increasing allowance to "
                f"{Decimal(candidate['allowance_percent']):.2f}% materially improves "
                "formation coverage"
            )
            if wider_rows and all(
                int(row["hypothetical_activations"]) == candidate_activations
                for row in wider_rows
            ):
                candidate_statement += (
                    " while wider allowances provide no additional MRZ formations"
                )
            interpretation_parts.append(candidate_statement + ".")
        elif increases:
            interpretation_parts.append(
                "At least one tested allowance increase admitted additional symbol-route "
                "histories."
            )
        else:
            interpretation_parts.append(
                "No tested allowance increase admitted an additional symbol-route history."
            )
        interpretation_parts.append(
            f"The {production['minimum_observations']}-observation requirement remains the "
            "primary confidence control."
        )
        current_near_miss_count = len(current_near_misses)
        historical_near_miss_count = len(historical_near_misses)
        interpretation_parts.append(
            f"The report identified {current_near_miss_count} current production "
            f"near {'miss' if current_near_miss_count == 1 else 'misses'} and "
            f"{historical_near_miss_count} closest historical production near "
            f"{'miss' if historical_near_miss_count == 1 else 'misses'} within the "
            "tested 1.00%–2.00% range."
        )
        interpretation_parts.append(
            "More eligible symbol-route histories are required before considering any "
            "production-policy change."
        )
        interpretation_parts.append(
            "These are observed historical frequencies and should not be interpreted "
            "as predictive probabilities."
        )
        evidence_interpretation = {
            "code": "EVIDENCE_INTERPRETATION_PRELIMINARY" if preliminary else "EVIDENCE_INTERPRETATION_OBSERVED",
            "heading": "Evidence interpretation",
            "text": " ".join(interpretation_parts),
            "numerator": production_activated,
            "denominator": production_eligible,
            "scenario_ids": [production_id],
            "small_sample": preliminary,
        }

        return {
            "sample_assessment": sample,
            "production_feasibility": production_feasibility,
            "count_sensitivity": count_sensitivity,
            "allowance_sensitivity": allowance_sensitivity,
            "algorithm_comparison": algorithm_comparison,
            "candidate_policy_evaluation": candidate_policy_evaluation,
            "current_production_near_misses": current_near_misses,
            "closest_production_near_misses": historical_near_misses,
            "evidence_interpretation": evidence_interpretation,
        }
