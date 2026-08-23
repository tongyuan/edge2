from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Callable, Sequence

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

    @property
    def minimum_required_allowance_pct(self) -> Decimal | None:
        """Exact candidate span as a percentage of the full IPDA width."""
        return (
            self.normalized_span * Decimal("100")
            if self.normalized_span is not None
            else None
        )

    @property
    def configured_allowance_pct(self) -> Decimal:
        return self.concentration_threshold * Decimal("100")

    @property
    def allowance_difference_pct_points(self) -> Decimal | None:
        required = self.minimum_required_allowance_pct
        return None if required is None else required - self.configured_allowance_pct

    @property
    def allowance_comparison(self) -> str | None:
        difference = self.allowance_difference_pct_points
        if difference is None:
            return None
        if difference > 0:
            return "SHORTFALL"
        if difference < 0:
            return "MARGIN"
        return "AT_THRESHOLD"


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


SeedSelector = Callable[
    [Sequence[Observation], str, Decimal, int, Decimal],
    _SeedSelection,
]


def latest_route_window(observations: Sequence[Observation]) -> list[Observation]:
    return sorted(observations, key=lambda item: item.order_key)[-ROUTE_OBSERVATION_WINDOW:]


def expand_selected_seed(
    observations: Sequence[Observation],
    selected_seed: Sequence[Observation],
    ipda_width: Decimal,
    minimum_required_count: int,
    concentration_threshold: Decimal,
    *,
    tested_window_count: int,
) -> _SeedSelection:
    """Apply production price-space expansion to an already chosen seed.

    The feasibility service uses this shared primitive for its chronological
    shadow seed so Algorithm B differs only in how the initial seed is chosen.
    """
    if len(selected_seed) != minimum_required_count:
        raise ValueError("selected_seed must contain minimum_required_count observations")
    if not ipda_width.is_finite() or ipda_width <= 0:
        raise ValueError("ipda_width must be finite and positive")
    if not concentration_threshold.is_finite() or concentration_threshold <= 0:
        raise ValueError("concentration_threshold must be finite and positive")

    price_sorted = sorted(
        observations,
        key=lambda item: (item.observation_price, item.order_key),
    )
    selected_ids = {item.event_id for item in selected_seed}
    positions = [
        index for index, item in enumerate(price_sorted) if item.event_id in selected_ids
    ]
    if len(positions) != len(selected_seed):
        raise ValueError("selected_seed must belong to observations")

    selected_seed_sorted = tuple(price_sorted[index] for index in positions)
    selected_lower = selected_seed_sorted[0].observation_price
    selected_upper = selected_seed_sorted[-1].observation_price
    observed_span = selected_upper - selected_lower
    maximum_span = concentration_threshold * ipda_width
    if observed_span > maximum_span:
        return _SeedSelection(
            None,
            tested_window_count,
            selected_seed_sorted,
            selected_lower,
            selected_upper,
            observed_span,
            False,
        )

    left = positions[0]
    right = positions[-1]
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
        tested_window_count,
        selected_seed_sorted,
        selected_lower,
        selected_upper,
        observed_span,
        True,
    )


def _select_seed_and_cluster(
    observations: Sequence[Observation],
    incoming_event_id: str,
    ipda_width: Decimal,
    minimum_required_count: int = MIN_CLUSTER_OBSERVATIONS,
    concentration_threshold: Decimal = CONCENTRATION_SPAN_THRESHOLD,
) -> _SeedSelection:
    if len(observations) < minimum_required_count:
        return _SeedSelection(None, 0, (), None, None, None, False)
    if minimum_required_count < 1:
        raise ValueError("minimum_required_count must be positive")
    if not concentration_threshold.is_finite() or concentration_threshold <= 0:
        raise ValueError("concentration_threshold must be finite and positive")
    if not ipda_width.is_finite() or ipda_width <= 0:
        raise ValueError("ipda_width must be finite and positive")

    price_sorted = sorted(
        observations,
        key=lambda item: (item.observation_price, item.order_key),
    )
    seeds: list[
        tuple[
            tuple[Decimal, Decimal, Decimal, tuple[tuple[object, ...], ...], int],
            tuple[Observation, ...],
        ]
    ] = []
    for start in range(0, len(price_sorted) - minimum_required_count + 1):
        window = tuple(price_sorted[start : start + minimum_required_count])
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

    _seed_key, selected_seed = min(seeds, key=lambda item: item[0])
    return expand_selected_seed(
        price_sorted,
        selected_seed,
        ipda_width,
        minimum_required_count,
        concentration_threshold,
        tested_window_count=len(seeds),
    )


def evaluate_concentration(
    observations: Sequence[Observation],
    route: Route,
    *,
    minimum_required_count: int = MIN_CLUSTER_OBSERVATIONS,
    concentration_threshold: Decimal = CONCENTRATION_SPAN_THRESHOLD,
    seed_selector: SeedSelector | None = None,
) -> ConcentrationEvaluation:
    if minimum_required_count < 1:
        raise ValueError("minimum_required_count must be positive")
    if not concentration_threshold.is_finite() or concentration_threshold <= 0:
        raise ValueError("concentration_threshold must be finite and positive")
    route_observations = tuple(item for item in observations if item.route is route)
    retained = tuple(latest_route_window(route_observations))
    newest = retained[-1] if retained else None
    if newest is None:
        return ConcentrationEvaluation(
            cluster=None,
            diagnostic=ConcentrationDiagnostic(
                route=route,
                retained_observation_count=0,
                minimum_required_count=minimum_required_count,
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
                concentration_threshold=concentration_threshold,
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
    allowance = concentration_threshold * ipda_width
    if len(retained) < minimum_required_count:
        return ConcentrationEvaluation(
            cluster=None,
            diagnostic=ConcentrationDiagnostic(
                route=route,
                retained_observation_count=len(retained),
                minimum_required_count=minimum_required_count,
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
                concentration_threshold=concentration_threshold,
                allowance=allowance,
                normalized_span=None,
                proposed_midpoint=None,
                proposed_structural_location=None,
                concentration_passed=False,
                structural_eligibility_passed=None,
                result=ConcentrationResult.INSUFFICIENT_OBSERVATIONS,
            ),
        )

    selector = seed_selector or _select_seed_and_cluster
    selection = selector(
        retained,
        newest.event_id,
        ipda_width,
        minimum_required_count,
        concentration_threshold,
    )
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
                minimum_required_count=minimum_required_count,
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
                concentration_threshold=concentration_threshold,
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
            minimum_required_count=minimum_required_count,
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
            concentration_threshold=concentration_threshold,
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
