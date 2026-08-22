from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Sequence

from app.domain import Cluster, Observation, PriceLocation, Route
from app.structure import classify_ipda_location, classify_structural_location


MIN_CLUSTER_OBSERVATIONS = 4
ROUTE_OBSERVATION_WINDOW = 20
CONCENTRATION_SPAN_THRESHOLD = Decimal("0.01")


class ConcentrationResult(StrEnum):
    INSUFFICIENT_OBSERVATIONS = "INSUFFICIENT_OBSERVATIONS"
    TOO_DISPERSED = "TOO_DISPERSED"
    STRUCTURALLY_INELIGIBLE = "STRUCTURALLY_INELIGIBLE"
    QUALIFIES = "QUALIFIES"


@dataclass(frozen=True, slots=True)
class ConcentrationDiagnostic:
    route: Route
    retained_observation_count: int
    minimum_required_count: int
    newest_observation_id: str | None
    newest_observation_included: bool
    tested_window_count: int
    selected_observation_ids: tuple[str, ...]
    selected_observation_count: int
    selected_lower: Decimal | None
    selected_upper: Decimal | None
    observed_span: Decimal | None
    ipda_20w_high: Decimal | None
    ipda_20w_low: Decimal | None
    ipda_width: Decimal | None
    concentration_threshold: Decimal
    allowance: Decimal | None
    normalized_span: Decimal | None
    proposed_midpoint: Decimal | None
    proposed_structural_location: PriceLocation | None
    concentration_passed: bool
    structural_eligibility_passed: bool | None
    result: ConcentrationResult


@dataclass(frozen=True, slots=True)
class ConcentrationEvaluation:
    cluster: Cluster | None
    diagnostic: ConcentrationDiagnostic

    @property
    def result(self) -> ConcentrationResult:
        return self.diagnostic.result


@dataclass(frozen=True, slots=True)
class _SeedSelection:
    cluster: Cluster | None
    tested_window_count: int
    selected_seed: tuple[Observation, ...]
    selected_lower: Decimal | None
    selected_upper: Decimal | None
    observed_span: Decimal | None
    concentration_passed: bool


def latest_route_window(observations: Sequence[Observation]) -> list[Observation]:
    return sorted(observations, key=lambda item: item.order_key)[-ROUTE_OBSERVATION_WINDOW:]


def _select_seed_and_cluster(
    observations: Sequence[Observation],
    incoming_event_id: str,
    ipda_width: Decimal,
) -> _SeedSelection:
    if len(observations) < MIN_CLUSTER_OBSERVATIONS:
        return _SeedSelection(None, 0, (), None, None, None, False)
    if not ipda_width.is_finite() or ipda_width <= 0:
        raise ValueError("ipda_width must be finite and positive")

    price_sorted = sorted(
        observations,
        key=lambda item: (item.observation_price, item.order_key),
    )
    maximum_span = CONCENTRATION_SPAN_THRESHOLD * ipda_width
    seeds: list[
        tuple[
            tuple[Decimal, Decimal, Decimal, tuple[tuple[object, ...], ...], int],
            tuple[Observation, ...],
        ]
    ] = []
    for start in range(0, len(price_sorted) - MIN_CLUSTER_OBSERVATIONS + 1):
        window = tuple(price_sorted[start : start + MIN_CLUSTER_OBSERVATIONS])
        if not any(item.event_id == incoming_event_id for item in window):
            continue
        span = window[-1].observation_price - window[0].observation_price
        seeds.append(
            (
                (
                    span,
                    window[0].observation_price,
                    window[-1].observation_price,
                    tuple(item.order_key for item in window),
                    start,
                ),
                window,
            )
        )
    if not seeds:
        return _SeedSelection(None, 0, (), None, None, None, False)

    seed_key, selected_seed = min(seeds, key=lambda item: item[0])
    observed_span, selected_lower, selected_upper, _orders, seed_start = seed_key
    if observed_span > maximum_span:
        return _SeedSelection(
            None,
            len(seeds),
            selected_seed,
            selected_lower,
            selected_upper,
            observed_span,
            False,
        )

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
    cluster = Cluster(
        members=members,
        lower=lower,
        upper=upper,
        midpoint=(lower + upper) / Decimal("2"),
        normalized_span=span / ipda_width,
    )
    return _SeedSelection(
        cluster,
        len(seeds),
        selected_seed,
        selected_lower,
        selected_upper,
        observed_span,
        True,
    )


def evaluate_concentration(
    observations: Sequence[Observation],
    route: Route,
) -> ConcentrationEvaluation:
    route_observations = tuple(item for item in observations if item.route is route)
    retained = tuple(latest_route_window(route_observations))
    newest = retained[-1] if retained else None
    if newest is None:
        return ConcentrationEvaluation(
            cluster=None,
            diagnostic=ConcentrationDiagnostic(
                route=route,
                retained_observation_count=0,
                minimum_required_count=MIN_CLUSTER_OBSERVATIONS,
                newest_observation_id=None,
                newest_observation_included=False,
                tested_window_count=0,
                selected_observation_ids=(),
                selected_observation_count=0,
                selected_lower=None,
                selected_upper=None,
                observed_span=None,
                ipda_20w_high=None,
                ipda_20w_low=None,
                ipda_width=None,
                concentration_threshold=CONCENTRATION_SPAN_THRESHOLD,
                allowance=None,
                normalized_span=None,
                proposed_midpoint=None,
                proposed_structural_location=None,
                concentration_passed=False,
                structural_eligibility_passed=None,
                result=ConcentrationResult.INSUFFICIENT_OBSERVATIONS,
            ),
        )

    ipda_width = newest.ipda_width
    if not ipda_width.is_finite() or ipda_width <= 0:
        raise ValueError("ipda_width must be finite and positive")
    allowance = CONCENTRATION_SPAN_THRESHOLD * ipda_width
    if len(retained) < MIN_CLUSTER_OBSERVATIONS:
        return ConcentrationEvaluation(
            cluster=None,
            diagnostic=ConcentrationDiagnostic(
                route=route,
                retained_observation_count=len(retained),
                minimum_required_count=MIN_CLUSTER_OBSERVATIONS,
                newest_observation_id=newest.event_id,
                newest_observation_included=False,
                tested_window_count=0,
                selected_observation_ids=(),
                selected_observation_count=0,
                selected_lower=None,
                selected_upper=None,
                observed_span=None,
                ipda_20w_high=newest.ipda_20w_high,
                ipda_20w_low=newest.ipda_20w_low,
                ipda_width=ipda_width,
                concentration_threshold=CONCENTRATION_SPAN_THRESHOLD,
                allowance=allowance,
                normalized_span=None,
                proposed_midpoint=None,
                proposed_structural_location=None,
                concentration_passed=False,
                structural_eligibility_passed=None,
                result=ConcentrationResult.INSUFFICIENT_OBSERVATIONS,
            ),
        )

    selection = _select_seed_and_cluster(retained, newest.event_id, ipda_width)
    selected_ids = tuple(item.event_id for item in selection.selected_seed)
    normalized_span = (
        selection.observed_span / ipda_width
        if selection.observed_span is not None
        else None
    )
    if not selection.concentration_passed:
        proposed_midpoint = (
            (selection.selected_lower + selection.selected_upper) / Decimal("2")
            if selection.selected_lower is not None and selection.selected_upper is not None
            else None
        )
        proposed_location = (
            classify_ipda_location(
                proposed_midpoint,
                newest.ipda_20w_high,
                newest.ipda_20w_low,
            )
            if proposed_midpoint is not None
            else None
        )
        structurally_eligible = (
            classify_structural_location(
                route,
                proposed_midpoint,
                newest.ipda_20w_high,
                newest.ipda_20w_low,
            ) is not None
            if proposed_midpoint is not None
            else None
        )
        return ConcentrationEvaluation(
            cluster=None,
            diagnostic=ConcentrationDiagnostic(
                route=route,
                retained_observation_count=len(retained),
                minimum_required_count=MIN_CLUSTER_OBSERVATIONS,
                newest_observation_id=newest.event_id,
                newest_observation_included=newest.event_id in selected_ids,
                tested_window_count=selection.tested_window_count,
                selected_observation_ids=selected_ids,
                selected_observation_count=len(selected_ids),
                selected_lower=selection.selected_lower,
                selected_upper=selection.selected_upper,
                observed_span=selection.observed_span,
                ipda_20w_high=newest.ipda_20w_high,
                ipda_20w_low=newest.ipda_20w_low,
                ipda_width=ipda_width,
                concentration_threshold=CONCENTRATION_SPAN_THRESHOLD,
                allowance=allowance,
                normalized_span=normalized_span,
                proposed_midpoint=proposed_midpoint,
                proposed_structural_location=proposed_location,
                concentration_passed=False,
                structural_eligibility_passed=structurally_eligible,
                result=ConcentrationResult.TOO_DISPERSED,
            ),
        )

    cluster = selection.cluster
    if cluster is None:
        raise RuntimeError("passing concentration must produce a cluster")
    proposed_location = classify_ipda_location(
        cluster.midpoint,
        newest.ipda_20w_high,
        newest.ipda_20w_low,
    )
    structurally_eligible = classify_structural_location(
        route,
        cluster.midpoint,
        newest.ipda_20w_high,
        newest.ipda_20w_low,
    ) is not None
    result = (
        ConcentrationResult.QUALIFIES
        if structurally_eligible
        else ConcentrationResult.STRUCTURALLY_INELIGIBLE
    )
    return ConcentrationEvaluation(
        cluster=cluster,
        diagnostic=ConcentrationDiagnostic(
            route=route,
            retained_observation_count=len(retained),
            minimum_required_count=MIN_CLUSTER_OBSERVATIONS,
            newest_observation_id=newest.event_id,
            newest_observation_included=newest.event_id in selected_ids,
            tested_window_count=selection.tested_window_count,
            selected_observation_ids=selected_ids,
            selected_observation_count=len(selected_ids),
            selected_lower=selection.selected_lower,
            selected_upper=selection.selected_upper,
            observed_span=selection.observed_span,
            ipda_20w_high=newest.ipda_20w_high,
            ipda_20w_low=newest.ipda_20w_low,
            ipda_width=ipda_width,
            concentration_threshold=CONCENTRATION_SPAN_THRESHOLD,
            allowance=allowance,
            normalized_span=normalized_span,
            proposed_midpoint=cluster.midpoint,
            proposed_structural_location=proposed_location,
            concentration_passed=True,
            structural_eligibility_passed=structurally_eligible,
            result=result,
        ),
    )


def select_cluster(
    observations: Sequence[Observation],
    incoming_event_id: str,
    ipda_width: Decimal,
) -> Cluster | None:
    """Compatibility wrapper over the diagnostic-producing seed calculation."""
    return _select_seed_and_cluster(observations, incoming_event_id, ipda_width).cluster
