from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any, Mapping, Sequence


# Diagnosis-only controls. They do not participate in production concentration.
# The evaluator retains arbitrary decimal precision but the operator surface displays
# allowance to two decimals. With no trustworthy local episode sample to estimate
# natural variation, 0.02pp conservatively treats a one-hundredth movement as stable.
CONCENTRATION_TREND_EPSILON_PP = Decimal("0.02")
NEAR_MISS_DIAGNOSIS_LOOKBACK_EPISODES = 5


class ConcentrationTrend(StrEnum):
    TIGHTENING = "TIGHTENING"
    STABLE = "STABLE"
    WIDENING = "WIDENING"
    MIXED = "MIXED"


class NearMissDiagnosis(StrEnum):
    CONVERGING = "CONVERGING"
    PERSISTENT = "PERSISTENT"
    DISPERSING = "DISPERSING"
    INCONSISTENT = "INCONSISTENT"


DIAGNOSIS_TEXT = {
    NearMissDiagnosis.CONVERGING: (
        "Repeated same-area near misses are becoming more tightly concentrated "
        "toward the 1.00% production threshold."
    ),
    NearMissDiagnosis.PERSISTENT: (
        "Repeated same-area near misses are maintaining similar concentration."
    ),
    NearMissDiagnosis.DISPERSING: (
        "The area continues to recur, but concentration is widening away from the "
        "1.00% production threshold."
    ),
    NearMissDiagnosis.INCONSISTENT: (
        "Historical near-miss episodes do not yet show a consistent recurring "
        "concentration pattern."
    ),
}


STRUCTURAL_LOCATION_LABELS = {
    "deep_discount_core_mrz": "Deep Discount",
    "shallow_discount_core_mrz": "Shallow Discount",
    "shallow_premium_core_mrz": "Shallow Premium",
    "deep_premium_core_mrz": "Deep Premium",
}


def classify_concentration_trend(
    allowances: Sequence[Decimal],
    *,
    epsilon_pp: Decimal = CONCENTRATION_TREND_EPSILON_PP,
) -> ConcentrationTrend | None:
    """Classify chronological allowance transitions for diagnosis only."""
    if len(allowances) < 2:
        return None
    movements: set[ConcentrationTrend] = set()
    for previous, current in zip(allowances, allowances[1:]):
        delta = current - previous
        if delta < -epsilon_pp:
            movements.add(ConcentrationTrend.TIGHTENING)
        elif delta > epsilon_pp:
            movements.add(ConcentrationTrend.WIDENING)
    if not movements:
        return ConcentrationTrend.STABLE
    if movements == {ConcentrationTrend.TIGHTENING}:
        return ConcentrationTrend.TIGHTENING
    if movements == {ConcentrationTrend.WIDENING}:
        return ConcentrationTrend.WIDENING
    return ConcentrationTrend.MIXED


def ranges_overlap(
    current_lower: Decimal,
    current_upper: Decimal,
    prior_lower: Decimal,
    prior_upper: Decimal,
) -> bool:
    """Inclusive intersection: partial overlap, containment and touching qualify."""
    return current_upper >= prior_lower and current_lower <= prior_upper


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat().replace("+00:00", "Z")
    return str(value)


def _decimal_text(value: Any) -> str:
    return str(Decimal(str(value)))


def _historical_episode(row: Mapping[str, Any]) -> dict[str, Any]:
    location = str(row["canonical_structural_location"])
    return {
        "episode_id": int(row["id"]),
        "candidate_identity": str(row["canonical_candidate_identity"]),
        "symbol": str(row["symbol"]),
        "route": str(row["route_owner"]),
        "candidate_lower_boundary": _decimal_text(row["canonical_candidate_lower"]),
        "candidate_upper_boundary": _decimal_text(row["canonical_candidate_upper"]),
        "candidate_midpoint": _decimal_text(row["canonical_candidate_midpoint"]),
        "minimum_required_allowance_pct": _decimal_text(
            row["canonical_minimum_required_allowance_pct"]
        ),
        "candidate_observation_count": int(
            row["canonical_supporting_observation_count"]
        ),
        "candidate_timestamp": _iso(row["canonical_candidate_timestamp"]),
        "episode_started_at": _iso(row["started_at"]),
        "episode_ended_at": _iso(row["ended_at"]),
        "ended_reason": str(row["ended_reason"]),
        "structural_location": location,
        "structural_location_label": STRUCTURAL_LOCATION_LABELS.get(location),
        "status": "HISTORICAL",
        "canonical_snapshot_reliable": True,
    }


def _current_episode(
    candidate: Mapping[str, Any],
    open_row: Mapping[str, Any] | None,
) -> dict[str, Any]:
    location_value = candidate.get("structural_location")
    location = str(location_value) if location_value is not None else None
    return {
        "episode_id": int(open_row["id"]) if open_row is not None else None,
        "candidate_identity": str(candidate["candidate_identity"]),
        "symbol": str(candidate["symbol"]),
        "route": str(candidate["route"]),
        "candidate_lower_boundary": _decimal_text(
            candidate["candidate_lower_boundary"]
        ),
        "candidate_upper_boundary": _decimal_text(
            candidate["candidate_upper_boundary"]
        ),
        "candidate_midpoint": _decimal_text(candidate["candidate_midpoint"]),
        "minimum_required_allowance_pct": _decimal_text(
            candidate["minimum_required_allowance_pct"]
        ),
        "candidate_observation_count": int(candidate["candidate_observation_count"]),
        "candidate_timestamp": _iso(candidate["candidate_timestamp"]),
        "episode_started_at": (
            _iso(open_row["started_at"])
            if open_row is not None
            else _iso(candidate["candidate_timestamp"])
        ),
        "episode_ended_at": None,
        "ended_reason": None,
        "structural_location": location,
        "structural_location_label": STRUCTURAL_LOCATION_LABELS.get(location),
        "status": "CURRENT",
        "canonical_snapshot_reliable": True,
    }


def build_near_miss_diagnosis(
    candidate: Mapping[str, Any],
    episode_rows: Sequence[Mapping[str, Any]],
    *,
    epsilon_pp: Decimal = CONCENTRATION_TREND_EPSILON_PP,
    lookback_episodes: int = NEAR_MISS_DIAGNOSIS_LOOKBACK_EPISODES,
) -> dict[str, Any]:
    """Combine durable distinct episodes with the live current candidate."""
    if lookback_episodes < 2:
        raise ValueError("lookback_episodes must be at least 2")
    symbol = str(candidate["symbol"])
    route = str(candidate["route"])
    same_population = [
        row
        for row in episode_rows
        if str(row["symbol"]) == symbol and str(row["route_owner"]) == route
    ]
    open_row = next((row for row in same_population if row["ended_at"] is None), None)
    trustworthy_closed = [
        row
        for row in same_population
        if row["ended_at"] is not None
        and bool(row.get("canonical_snapshot_reliable"))
    ]
    trustworthy_closed.sort(
        key=lambda row: (
            row["started_at"],
            int(row["id"]),
        )
    )
    detailed = [_historical_episode(row) for row in trustworthy_closed]
    detailed.append(_current_episode(candidate, open_row))
    window = detailed[-lookback_episodes:]
    included_ids = {id(item) for item in window}
    current_lower = Decimal(str(candidate["candidate_lower_boundary"]))
    current_upper = Decimal(str(candidate["candidate_upper_boundary"]))
    for number, episode in enumerate(detailed, 1):
        episode["episode_number"] = number
        episode["included_in_diagnosis"] = id(episode) in included_ids
        episode["overlaps_current"] = ranges_overlap(
            current_lower,
            current_upper,
            Decimal(episode["candidate_lower_boundary"]),
            Decimal(episode["candidate_upper_boundary"]),
        )

    allowances = [
        Decimal(episode["minimum_required_allowance_pct"]) for episode in window
    ]
    trend = classify_concentration_trend(allowances, epsilon_pp=epsilon_pp)
    same_area_count = sum(bool(episode["overlaps_current"]) for episode in window)
    recurring = same_area_count >= 2
    diagnosis: NearMissDiagnosis | None = None
    if trend is not None:
        if not recurring or trend is ConcentrationTrend.MIXED:
            diagnosis = NearMissDiagnosis.INCONSISTENT
        elif trend is ConcentrationTrend.TIGHTENING:
            diagnosis = NearMissDiagnosis.CONVERGING
        elif trend is ConcentrationTrend.STABLE:
            diagnosis = NearMissDiagnosis.PERSISTENT
        elif trend is ConcentrationTrend.WIDENING:
            diagnosis = NearMissDiagnosis.DISPERSING

    excluded_unreliable = sum(
        row["ended_at"] is not None
        and not bool(row.get("canonical_snapshot_reliable"))
        for row in same_population
    )
    return {
        "available": diagnosis is not None,
        "diagnosis": diagnosis.value if diagnosis is not None else None,
        "explanation": DIAGNOSIS_TEXT[diagnosis] if diagnosis is not None else None,
        "concentration_trend": trend.value if trend is not None else None,
        "episode_count": len(window),
        "same_area_count": same_area_count,
        "allowance_history": [_decimal_text(value) for value in allowances],
        "lookback_episode_limit": lookback_episodes,
        "concentration_trend_epsilon_pp": _decimal_text(epsilon_pp),
        "total_trustworthy_episode_count": len(detailed),
        "excluded_unreliable_episode_count": excluded_unreliable,
        "episodes": detailed,
    }
